"""MCP server exposing the HR Postgres database as tools.

Runs over stdio. The agent (src/agent.py) spawns this as a subprocess and
calls the tools through an MCP client session - the agent never touches
SQL directly.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
import db

mcp = FastMCP("hr-database")


@mcp.tool()
def get_leave_balance(employee_id: str) -> dict:
    """Get the annual leave balance for an employee, e.g. 'E102'.
    Returns total days, days used and days remaining for the current year."""
    employee_id = employee_id.strip().upper()
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT employee_id, full_name, annual_leave_total, annual_leave_used "
                "FROM employees WHERE employee_id = %s",
                (employee_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"error": f"No employee found with id {employee_id}"}
    total, used = row[2], row[3]
    return {
        "employee_id": row[0],
        "name": row[1],
        "annual_leave_total": total,
        "annual_leave_used": used,
        "annual_leave_remaining": total - used,
    }


@mcp.tool()
def get_employee_directory_entry(employee_id: str) -> dict:
    """Look up an employee's directory entry (department, manager, contact).
    NOTE: the contact fields are personal data - the agent's output guardrail
    redacts them before anything is shown to the user."""
    employee_id = employee_id.strip().upper()
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT employee_id, full_name, department, manager, email, phone "
                "FROM employees WHERE employee_id = %s",
                (employee_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"error": f"No employee found with id {employee_id}"}
    keys = ["employee_id", "name", "department", "manager", "email", "phone"]
    return dict(zip(keys, row))


@mcp.tool()
def get_it_asset(employee_id: str) -> dict:
    """Get the IT asset (company laptop) assigned to an employee, with its
    warranty end date."""
    employee_id = employee_id.strip().upper()
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT asset_tag, employee_id, device, issued_on, warranty_until "
                "FROM it_assets WHERE employee_id = %s",
                (employee_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"error": f"No IT asset found for employee {employee_id}"}
    return {
        "asset_tag": row[0],
        "employee_id": row[1],
        "device": row[2],
        "issued_on": str(row[3]),
        "warranty_until": str(row[4]),
    }


@mcp.tool()
def list_employees() -> list:
    """List all employees: id, name and department only (no contact details)."""
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT employee_id, full_name, department FROM employees ORDER BY employee_id")
            rows = cur.fetchall()
    return [{"employee_id": r[0], "name": r[1], "department": r[2]} for r in rows]


if __name__ == "__main__":
    mcp.run()
