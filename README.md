# mdo

Simple list manager with a single command:

```powershell
python mdo.py add "Buy milk"   # Added #0: Buy milk
python mdo.py add "Book flights"  # Added #1: Book flights
python mdo.py list
```

Tasks are stored in `items.json` with monotonically increasing numeric IDs that persist across runs.
Use `list` to display each task as `<id>: <text>`.
