import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect

app = Flask(__name__)
DB = "Library.db"
LOAN_DAYS = 7       # days allowed to keep a book
FINE_PER_DAY = 5    # fine per day when returned late


# ---------- database ----------
def run(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(sql, params)
        con.commit()
        rows = cur.fetchall()
    finally:
        con.close()
    return rows


def create_tables():
    run("""CREATE TABLE IF NOT EXISTS Members (
            memID INTEGER PRIMARY KEY,
            memFName TEXT,
            memLName TEXT,
            memContact TEXT)""")
    run("""CREATE TABLE IF NOT EXISTS Books (
            bookID INTEGER PRIMARY KEY,
            bookTitle TEXT,
            bookAuthor TEXT,
            bookYear INTEGER)""")
    run("""CREATE TABLE IF NOT EXISTS Borrowing (
            borRN INTEGER PRIMARY KEY AUTOINCREMENT,
            memID INTEGER,
            bookID INTEGER,
            borDate TEXT,
            borDue TEXT,
            borReturn TEXT,
            borStat TEXT,
            FOREIGN KEY (memID) REFERENCES Members(memID),
            FOREIGN KEY (bookID) REFERENCES Books(bookID))""")


def get_fine(due, returned, stat):
    if stat != "Returned":
        return 0
    d1 = datetime.strptime(due, "%Y-%m-%d")
    d2 = datetime.strptime(returned, "%Y-%m-%d")
    days_late = (d2 - d1).days
    if days_late > 0:
        return days_late * FINE_PER_DAY
    return 0


def add_fines(rows):
    # rows: borRN, memID, bookTitle, borDate, borDue, borReturn, borStat
    result = []
    for r in rows:
        fine = get_fine(r[4], r[5], r[6])
        result.append([r[0], r[1], r[2], r[3], r[4], r[5], r[6], fine])
    return result


def today():
    return datetime.now().strftime("%m/%d/%Y")


# ---------- menu ----------
@app.route("/")
def index():
    return render_template("index.html")


# ---------- members ----------
@app.route("/members")
def members():
    rows = run("SELECT * FROM Members ORDER BY memID")
    error = request.args.get("error")
    return render_template("members.html", rows=rows, error=error)


@app.route("/members/add", methods=["GET", "POST"])
def member_add():
    if request.method == "POST":
        try:
            run("INSERT INTO Members VALUES (?, ?, ?, ?)",
                (request.form["memID"], request.form["memFName"],
                 request.form["memLName"], request.form["memContact"]))
        except sqlite3.IntegrityError:
            return render_template("member_add.html", error="ID already exists.")
        return redirect("/members")
    return render_template("member_add.html", error="")


@app.route("/members/edit/<mem_id>", methods=["GET", "POST"])
def member_edit(mem_id):
    if request.method == "POST":
        run("UPDATE Members SET memFName=?, memLName=?, memContact=? WHERE memID=?",
            (request.form["memFName"], request.form["memLName"],
             request.form["memContact"], mem_id))
        return redirect("/members")
    m = run("SELECT * FROM Members WHERE memID=?", (mem_id,))[0]
    return render_template("member_edit.html", m=m)


@app.route("/members/delete/<mem_id>")
def member_delete(mem_id):
    try:
        run("DELETE FROM Members WHERE memID=?", (mem_id,))
    except sqlite3.IntegrityError:
        return redirect("/members?error=Member has borrowing records.")
    return redirect("/members")


# ---------- books ----------
@app.route("/books")
def books():
    rows = run("SELECT * FROM Books ORDER BY bookID")
    error = request.args.get("error")
    return render_template("books.html", rows=rows, error=error)


@app.route("/books/add", methods=["GET", "POST"])
def book_add():
    if request.method == "POST":
        try:
            run("INSERT INTO Books VALUES (?, ?, ?, ?)",
                (request.form["bookID"], request.form["bookTitle"],
                 request.form["bookAuthor"], request.form["bookYear"]))
        except sqlite3.IntegrityError:
            return render_template("book_add.html", error="ID already exists.")
        return redirect("/books")
    return render_template("book_add.html", error="")


@app.route("/books/edit/<book_id>", methods=["GET", "POST"])
def book_edit(book_id):
    if request.method == "POST":
        run("UPDATE Books SET bookTitle=?, bookAuthor=?, bookYear=? WHERE bookID=?",
            (request.form["bookTitle"], request.form["bookAuthor"],
             request.form["bookYear"], book_id))
        return redirect("/books")
    b = run("SELECT * FROM Books WHERE bookID=?", (book_id,))[0]
    return render_template("book_edit.html", b=b)


@app.route("/books/delete/<book_id>")
def book_delete(book_id):
    try:
        run("DELETE FROM Books WHERE bookID=?", (book_id,))
    except sqlite3.IntegrityError:
        return redirect("/books?error=Book has borrowing records.")
    return redirect("/books")


# ---------- borrowing ----------
@app.route("/borrowing")
def borrowing():
    rows = run("""SELECT borRN, memID, bookID, borDate, borDue, borReturn, borStat
                  FROM Borrowing ORDER BY borRN""")
    return render_template("borrowing.html", rows=rows)


@app.route("/borrowing/add", methods=["GET", "POST"])
def borrowing_add():
    mems = run("SELECT memID, memLName, memFName FROM Members")
    bks = run("SELECT bookID, bookTitle FROM Books")
    if request.method == "POST":
        book_id = request.form["bookID"]
        # a book that is still borrowed cannot be borrowed again
        busy = run("SELECT borRN FROM Borrowing WHERE bookID=? AND borStat='Borrowed'",
                   (book_id,))
        if len(busy) > 0:
            return render_template("borrowing_add.html", mems=mems, bks=bks,
                                   error="That book is still borrowed.")
        bor_date = request.form["borDate"]
        date_obj = datetime.strptime(bor_date, "%Y-%m-%d")
        due = (date_obj + timedelta(days=LOAN_DAYS)).strftime("%Y-%m-%d")
        run("""INSERT INTO Borrowing (memID, bookID, borDate, borDue, borReturn, borStat)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (request.form["memID"], book_id, bor_date, due, "", "Borrowed"))
        return redirect("/borrowing")
    return render_template("borrowing_add.html", mems=mems, bks=bks, error="")


@app.route("/borrowing/return/<rn>", methods=["GET", "POST"])
def borrowing_return(rn):
    if request.method == "POST":
        run("UPDATE Borrowing SET borReturn=?, borStat='Returned' WHERE borRN=?",
            (request.form["borReturn"], rn))
        return redirect("/borrowing")
    return render_template("borrowing_return.html", rn=rn)


@app.route("/borrowing/cancel/<rn>")
def borrowing_cancel(rn):
    run("UPDATE Borrowing SET borStat='Cancelled' WHERE borRN=?", (rn,))
    return redirect("/borrowing")


# ---------- monitoring ----------
@app.route("/monitor/member")
def monitor_member():
    mem_id = request.args.get("mem_id", "")
    mem = None
    records = []
    total_books = 0
    total_fine = 0
    error = ""
    if mem_id != "":
        found = run("SELECT * FROM Members WHERE memID=?", (mem_id,))
        if len(found) == 0:
            error = "Member not found."
        else:
            mem = found[0]
            rows = run("""SELECT Borrowing.borRN, Borrowing.memID, Books.bookTitle,
                                 Borrowing.borDate, Borrowing.borDue,
                                 Borrowing.borReturn, Borrowing.borStat
                          FROM Borrowing, Books
                          WHERE Borrowing.bookID = Books.bookID
                          AND Borrowing.memID = ? ORDER BY Borrowing.borRN""", (mem_id,))
            records = add_fines(rows)
            for r in records:
                if r[6] != "Cancelled":
                    total_books = total_books + 1
                total_fine = total_fine + r[7]
    return render_template("monitor_member.html", mem_id=mem_id, mem=mem,
                           records=records, total_books=total_books,
                           total_fine=total_fine, error=error, today=today())


@app.route("/monitor/range")
def monitor_range():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    records = []
    total_books = 0
    total_fine = 0
    if date_from != "" and date_to != "":
        rows = run("""SELECT Borrowing.borRN, Borrowing.memID, Books.bookTitle,
                             Borrowing.borDate, Borrowing.borDue,
                             Borrowing.borReturn, Borrowing.borStat
                      FROM Borrowing, Books
                      WHERE Borrowing.bookID = Books.bookID
                      AND Borrowing.borDate BETWEEN ? AND ?
                      ORDER BY Borrowing.borRN""", (date_from, date_to))
        records = add_fines(rows)
        for r in records:
            if r[6] != "Cancelled":
                total_books = total_books + 1
            total_fine = total_fine + r[7]
    return render_template("monitor_range.html", date_from=date_from, date_to=date_to,
                           records=records, total_books=total_books,
                           total_fine=total_fine, today=today())


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
