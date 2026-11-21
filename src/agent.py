"""HR/IT helpdesk agent.

Pipeline per question:
  1. Input guardrail  - block prompt-injection attempts.
  2. Scope control    - refuse anything that is not an HR or IT topic.
  3. Routing          - employee-specific questions -> HR Postgres via the MCP
                        server; policy questions -> RAG over policy documents.
  4. Output guardrail - redact PII (emails, phone numbers, Aadhaar, PAN,
                        card numbers) from whatever goes back to the user.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import guardrails
import ollama_client
import rag

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCP_SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")

REFUSAL_OFF_TOPIC = (
    "I can only help with HR and IT topics - things like leave, benefits, "
    "policies, laptops, accounts and security. Your question looks outside "
    "that scope, so I can't help with it. For anything personal or general, "
    "please use another assistant."
)

BLOCKED_INJECTION = (
    "I can't process that request. It looks like an attempt to override my "
    "instructions, and I don't change my behaviour based on prompts like "
    "that. If you have a genuine HR or IT question, I'm happy to help."
)

DEFAULT_EMPLOYEE = os.environ.get("DEMO_EMPLOYEE_ID", "E101")


class HelpdeskAgent:
    def __init__(self):
        self.collection = None

    # ------------------------------------------------------------ mcp calls
    async def _call_mcp_tool(self, tool_name, arguments):
        env = dict(os.environ)
        params = StdioServerParameters(
            command=sys.executable, args=[MCP_SERVER_SCRIPT], env=env
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                import json
                text = result.content[0].text
                return json.loads(text)

    def call_mcp_tool(self, tool_name, arguments):
        return asyncio.run(self._call_mcp_tool(tool_name, arguments))

    # --------------------------------------------------------------- scope
    def _llm_scope_check(self, question):
        """Fallback scope check for questions with no keyword match."""
        try:
            reply = ollama_client.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You classify employee questions. Reply with exactly one word: "
                            "HR_IT if the question is about workplace HR or IT topics "
                            "(leave, benefits, policies, devices, accounts, security), "
                            "otherwise OTHER. Reply with that one word and nothing else."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                temperature=0,
            )
            verdict = reply.strip().upper().replace("-", "_").split()[0] if reply.strip() else ""
            return verdict == "HR_IT"
        except Exception:
            return False

    # -------------------------------------------------------------- routing
    def _answer_with_mcp(self, question, employee_id):
        """Pick the right MCP tool and format a precise, template-based answer."""
        q = question.lower()
        if "leave" in q or "vacation" in q or "holiday" in q:
            data = self.call_mcp_tool("get_leave_balance", {"employee_id": employee_id})
            if "error" in data:
                return data["error"] + ". Please check the employee id.", ["mcp:get_leave_balance"]
            return (
                f"{data['name']} ({data['employee_id']}) has {data['annual_leave_remaining']} "
                f"annual leave days remaining this year: {data['annual_leave_used']} used out of "
                f"{data['annual_leave_total']} total.",
                ["mcp:get_leave_balance"],
            )
        if any(k in q for k in ("laptop", "asset", "device", "warranty", "macbook", "thinkpad")):
            data = self.call_mcp_tool("get_it_asset", {"employee_id": employee_id})
            if "error" in data:
                return data["error"] + ".", ["mcp:get_it_asset"]
            return (
                f"Employee {data['employee_id']} is assigned a {data['device']} "
                f"(asset tag {data['asset_tag']}), issued on {data['issued_on']}. "
                f"The warranty runs until {data['warranty_until']}.",
                ["mcp:get_it_asset"],
            )
        if "list" in q and "employee" in q:
            data = self.call_mcp_tool("list_employees", {})
            lines = [f"- {e['employee_id']}: {e['name']} ({e['department']})" for e in data]
            return "Employees:\n" + "\n".join(lines), ["mcp:list_employees"]
        data = self.call_mcp_tool("get_employee_directory_entry", {"employee_id": employee_id})
        if "error" in data:
            return data["error"] + ". Please check the employee id.", ["mcp:get_employee_directory_entry"]
        return (
            f"{data['name']} ({data['employee_id']}) works in {data['department']} "
            f"and reports to {data['manager']}. Contact on record: {data['email']}, {data['phone']}.",
            ["mcp:get_employee_directory_entry"],
        )

    # ---------------------------------------------------------------- main
    def ask(self, question):
        """Answer one question. Returns a dict with the answer and an audit trail."""
        trail = {"question": question, "route": None, "guardrails": [], "sources": []}

        # 1. input guardrail: prompt injection
        is_injection, pattern = guardrails.detect_prompt_injection(question)
        if is_injection:
            trail["route"] = "blocked"
            trail["guardrails"].append("prompt_injection_blocked")
            trail["answer"] = BLOCKED_INJECTION
            return trail

        # 2/3. scope + routing
        employee_id = guardrails.find_employee_id(question)
        if employee_id is None and (" my " in f" {question.lower()} " or question.lower().startswith("my ")):
            employee_id = DEFAULT_EMPLOYEE  # demo session user
            trail["guardrails"].append(f"defaulted_to_session_employee:{DEFAULT_EMPLOYEE}")

        if employee_id:
            trail["route"] = "mcp"
            answer, tools = self._answer_with_mcp(question, employee_id)
            trail["sources"] = tools
        elif guardrails.is_hr_it_topic(question):
            trail["route"] = "rag"
            if self.collection is None:
                self.collection = rag.build_collection()
            answer, sources = rag.answer_policy_question(self.collection, question)
            trail["sources"] = sources
        elif self._llm_scope_check(question):
            trail["route"] = "rag"
            if self.collection is None:
                self.collection = rag.build_collection()
            answer, sources = rag.answer_policy_question(self.collection, question)
            trail["sources"] = sources
        else:
            trail["route"] = "refused"
            trail["guardrails"].append("out_of_scope_refused")
            trail["answer"] = REFUSAL_OFF_TOPIC
            return trail

        # 4. output guardrail: PII redaction
        redacted, kinds = guardrails.redact_pii(answer)
        if kinds:
            trail["guardrails"].append("pii_redacted:" + ",".join(sorted(set(kinds))))
        trail["answer"] = redacted
        return trail


def main():
    import db

    seeded = db.seed_if_empty()
    print("HR database ready" + (" (seeded demo data)" if seeded else ""))
    agent = HelpdeskAgent()
    print(f"Helpdesk agent ready. You are signed in as {DEFAULT_EMPLOYEE}.")
    print("Ask an HR/IT question (or 'quit'):\n")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() in ("quit", "exit"):
            break
        result = agent.ask(question)
        print(f"\n[{result['route']}] {result['answer']}")
        if result["guardrails"]:
            print(f"(guardrails: {', '.join(result['guardrails'])})")
        print()


if __name__ == "__main__":
    main()
