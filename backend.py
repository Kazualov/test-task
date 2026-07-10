from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import os

app = FastAPI(
    title="LD LATTE Calendar API",
    description="API для бронирования встреч сотрудников (Тестовое задание)"
)

DB_FILE = "meetings.db"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS meetings (
                                                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                           user_name TEXT NOT NULL,
                                                           partner_name TEXT NOT NULL,
                                                           start_time DATETIME NOT NULL,
                                                           end_time DATETIME NOT NULL
                   )
                   ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

# Pydantic-модель для валидации входящих данных
class Meeting(BaseModel):
    user_name: str
    partner_name: str
    start_time: datetime
    end_time: datetime

@app.post("/book", summary="Запланировать встречу")
def book_meeting(meeting: Meeting):
    if meeting.start_time >= meeting.end_time:
        raise HTTPException(status_code=400, detail="Время окончания должно быть позже времени начала.")
    if meeting.user_name.lower() == meeting.partner_name.lower():
        raise HTTPException(status_code=400, detail="Нельзя назначить встречу с самим собой.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Проверка пересечений: ищем, занят ли хоть один из участников в это время
    # Логика пересечения отрезков: (new_start < existing_end) AND (new_end > existing_start)
    cursor.execute('''
                   SELECT user_name, partner_name, start_time, end_time
                   FROM meetings
                   WHERE (
                       LOWER(user_name) = ? OR LOWER(user_name) = ? OR
                       LOWER(partner_name) = ? OR LOWER(partner_name) = ?
                       ) AND (
                       start_time < ? AND end_time > ?
                       )
                   ''', (
                       meeting.user_name.lower(), meeting.partner_name.lower(),
                       meeting.user_name.lower(), meeting.partner_name.lower(),
                       meeting.end_time, meeting.start_time
                   ))

    overlap = cursor.fetchone()

    if overlap:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Слот занят. У одного из участников уже есть встреча на это время."
        )

    # Если пересечений нет, добавляем встречу
    cursor.execute('''
                   INSERT INTO meetings (user_name, partner_name, start_time, end_time)
                   VALUES (?, ?, ?, ?)
                   ''', (meeting.user_name, meeting.partner_name, meeting.start_time, meeting.end_time))

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Встреча успешно запланирована!"}

@app.get("/schedule", summary="Посмотреть расписание")
def get_schedule(date: str = Query(None, description="Фильтр по дате (YYYY-MM-DD)")):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if date:
        cursor.execute('''
                       SELECT id, user_name, partner_name, start_time, end_time
                       FROM meetings
                       WHERE DATE(start_time) = ?
                       ORDER BY start_time
                       ''', (date,))
    else:
        cursor.execute('''
                       SELECT id, user_name, partner_name, start_time, end_time
                       FROM meetings
                       ORDER BY start_time
                       ''')

    rows = cursor.fetchall()
    conn.close()

    meetings = []
    for row in rows:
        meetings.append({
            "id": row[0],
            "user_name": row[1],
            "partner_name": row[2],
            "start_time": row[3],
            "end_time": row[4]
        })

    return {"meetings": meetings}