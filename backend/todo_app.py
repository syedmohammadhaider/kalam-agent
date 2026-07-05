import json

class TodoApp:
    def __init__(self, filename='todo.json'):
        self.filename = filename
        self.todos = []
        self.load_todos()

    def load_todos(self):
        try:
            with open(self.filename, 'r') as file:
                self.todos = json.load(file)
        except FileNotFoundError:
            self.todos = []

    def save_todos(self):
        with open(self.filename, 'w') as file:
            json.dump(self.todos, file, indent=4)

    def add_todo(self, task):
        self.todos.append(task)
        self.save_todos()

    def list_todos(self):
        return self.todos