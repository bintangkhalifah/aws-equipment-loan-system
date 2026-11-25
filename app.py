import os
import pymysql
from flask import Flask, jsonify, request

app = Flask(__name__)

VALID_STATUS = ("borrowed", "returned")
COLUMNS = (
    "id, equipment_name, borrower_name, "
    "CAST(loan_date AS CHAR) AS loan_date, "
    "CAST(return_date AS CHAR) AS return_date, status"
)


def get_conn():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "loansdb"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def query(sql, params=(), fetch=False):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch:
                return cur.fetchall()
            return cur.lastrowid, cur.rowcount
    finally:
        conn.close()


@app.get("/health")
def health():
    rows = query("SELECT 1 AS db_ok", (), fetch=True)
    return jsonify(rows[0])


@app.post("/loans")
def create_loan():
    d = request.get_json() or {}
    for field in ("equipment_name", "borrower_name", "loan_date"):
        if not d.get(field):
            return jsonify({"error": f"{field} is required"}), 400
    new_id, _ = query(
        "INSERT INTO loans (equipment_name, borrower_name, loan_date) "
        "VALUES (%s, %s, %s)",
        (d["equipment_name"], d["borrower_name"], d["loan_date"]),
    )
    return jsonify({"id": new_id}), 201


@app.get("/loans")
def list_loans():
    rows = query(f"SELECT {COLUMNS} FROM loans ORDER BY id", (), fetch=True)
    return jsonify(rows)


@app.put("/loans/<int:loan_id>")
def update_loan(loan_id):
    d = request.get_json() or {}
    if "status" in d and d["status"] not in VALID_STATUS:
        return jsonify({"error": "status must be borrowed or returned"}), 400
    _, n = query(
        "UPDATE loans SET "
        "equipment_name = COALESCE(%s, equipment_name), "
        "borrower_name = COALESCE(%s, borrower_name), "
        "loan_date = COALESCE(%s, loan_date), "
        "return_date = COALESCE(%s, return_date), "
        "status = COALESCE(%s, status) "
        "WHERE id = %s",
        (
            d.get("equipment_name"),
            d.get("borrower_name"),
            d.get("loan_date"),
            d.get("return_date"),
            d.get("status"),
            loan_id,
        ),
    )
    return jsonify({"updated": n})


@app.delete("/loans/<int:loan_id>")
def delete_loan(loan_id):
    _, n = query("DELETE FROM loans WHERE id = %s", (loan_id,))
    return jsonify({"deleted": n})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
