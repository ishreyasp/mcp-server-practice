import sqlite3
import aiosqlite
import os
import json
from fastmcp import FastMCP
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "expense.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP(name='ExpenseTracker')

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

init_db()        

@mcp.tool
async def add_expense(
    date, 
    amount: float, 
    category: str, 
    subcategory: str = "", 
    note = ""
):
    """Add new expense entry into database."""
    logger.info(f"Adding expense of {amount} for {category} on {date}")
    try:
        async with aiosqlite.connect(DB_PATH) as con:
            cur = await con.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (date, amount, category, subcategory, note)    
            )
            expense_id = cur.lastrowid
            await con.commit()

            return {"status": "success", "id": expense_id, "message": "Expense added successfully"}
    except Exception as e:
        if "readonly" in str(e).lower():
            logger.error(json.dumps({"status": "error", "message": "Database is in read-only mode. Check file permissions."}))
            return {"status": "error", "message": "Database is in read-only mode. Check file permissions."}
        logger.error(json.dumps({"status": "error", "message": f"Database error: {str(e)}"}))
        return {"status": "error", "message": f"Database error: {str(e)}"}


@mcp.tool
async def list_expense(start_date, end_date):
    """List expense entries within an inclusive date range."""
    logger.info(f"Retrieving expenses from {start_date} thru {end_date}")
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "SELECT id, date, amount, category, subcategory, note FROM expenses WHERE date BETWEEN ? AND ? ORDER BY id ASC",
                (start_date, end_date)
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        logger.error(json.dumps({"status": "error", "message": f"Error listing expenses: {str(e)}"}))
        return {"status": "error", "message": f"Error listing expenses: {str(e)}"}

@mcp.tool
async def summarize_expense(start_date, end_date, category=None):
    """Summarize expenses by category within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            query = (
                "SELECT category, SUM(amount) AS total_amount FROM expenses WHERE date BETWEEN ? AND ?"
            )
            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY category ASC"

            cur = await c.execute(query, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        logger.error(json.dumps({"status": "error", "message": f"Error summarizing expenses: {str(e)}"}))
        return {"status": "error", "message": f"Error summarizing expenses: {str(e)}"}

@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    try:
        default_categories = {
            "categories": [
                "Food & Dining",
                "Transportation",
                "Shopping",
                "Entertainment",
                "Bills & Utilities",
                "Healthcare",
                "Travel",
                "Education",
                "Business",
                "Other"
            ]
        }
        try:
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return json.dump(default_categories, indent=2)
    except Exception as e:
        logger.error(json.dumps({"error": "Could not load categories: {str(e)}"}))
        return f'{{"error": "Could not load categories: {str(e)}"}}'

if __name__ == '__main__':
    mcp.run()
    # mcp.run(transport="http", host="0.0.0.0", port=8000)