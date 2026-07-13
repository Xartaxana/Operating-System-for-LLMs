"""Простой todo-менеджер (CLI).

Использование:
    python todo.py add "текст задачи"
    python todo.py list
    python todo.py done <номер>
    python todo.py delete <номер>
"""
import json
import os
import sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")


def load():
    if os.path.exists(DB):
        with open(DB, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(tasks):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def cmd_add(text):
    tasks = load()
    tasks.append({"text": text, "done": False})
    save(tasks)
    print(f"добавлено под номером {len(tasks)}")


def cmd_list():
    tasks = load()
    if not tasks:
        print("список пуст")
        return
    for i, t in enumerate(tasks, 1):
        mark = "x" if t["done"] else " "
        print(f"{i}. [{mark}] {t['text']}")


def cmd_done(num):
    tasks = load()
    tasks[int(num) - 1]["done"] = True
    save(tasks)
    print(f"задача {num} отмечена выполненной")


def cmd_delete(num):
    tasks = load()
    removed = tasks.pop(int(num) - 1)
    save(tasks)
    print(f"удалено: {removed['text']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) >= 3:
        cmd_add(" ".join(sys.argv[2:]))
    elif cmd == "list":
        cmd_list()
    elif cmd == "done" and len(sys.argv) == 3:
        cmd_done(sys.argv[2])
    elif cmd == "delete" and len(sys.argv) == 3:
        cmd_delete(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
