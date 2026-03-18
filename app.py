from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List

DATA_FILE = Path(__file__).with_name('tasks.json')
AUTOSTART_DIR = Path.home() / '.config' / 'autostart'
AUTOSTART_FILE = AUTOSTART_DIR / 'task-list.desktop'
PRIORITY_ORDER = {"高": 0, "中": 1, "低": 2}
PRIORITY_COLORS = {"高": "#ff6b6b", "中": "#ffd166", "低": "#06d6a0"}
DATETIME_FORMAT = '%Y-%m-%d %H:%M'
REMINDER_OPTIONS = ['不提醒', '到期时', '提前5分钟', '提前15分钟', '提前30分钟', '提前60分钟']
REMINDER_MINUTES = {
    '不提醒': None,
    '到期时': 0,
    '提前5分钟': 5,
    '提前15分钟': 15,
    '提前30分钟': 30,
    '提前60分钟': 60,
}


@dataclass
class Task:
    title: str
    priority: str
    due_at: str = ''
    reminder_label: str = '不提醒'
    completed: bool = False
    reminded: bool = False

    def due_datetime(self) -> datetime | None:
        if not self.due_at:
            return None
        try:
            return datetime.strptime(self.due_at, DATETIME_FORMAT)
        except ValueError:
            return None

    def reminder_minutes(self) -> int | None:
        return REMINDER_MINUTES.get(self.reminder_label)


class TaskStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def load(self) -> List[Task]:
        if not self.file_path.exists():
            return []
        try:
            data = json.loads(self.file_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return []
        tasks: List[Task] = []
        for item in data:
            title = str(item.get('title', '')).strip()
            priority = item.get('priority', '中')
            due_at = str(item.get('due_at', '')).strip()
            reminder_label = item.get('reminder_label', '不提醒')
            completed = bool(item.get('completed', False))
            reminded = bool(item.get('reminded', False))
            if not title or priority not in PRIORITY_ORDER:
                continue
            if reminder_label not in REMINDER_MINUTES:
                reminder_label = '不提醒'
            if due_at:
                try:
                    datetime.strptime(due_at, DATETIME_FORMAT)
                except ValueError:
                    due_at = ''
                    reminder_label = '不提醒'
            tasks.append(
                Task(
                    title=title,
                    priority=priority,
                    due_at=due_at,
                    reminder_label=reminder_label,
                    completed=completed,
                    reminded=reminded,
                )
            )
        return tasks

    def save(self, tasks: List[Task]) -> None:
        payload = [asdict(task) for task in tasks]
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )


class TaskListApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('桌面任务列表')
        self.root.geometry('720x600')
        self.root.minsize(640, 500)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#111827')

        self.store = TaskStore(DATA_FILE)
        self.tasks = self.store.load()

        self.title_var = tk.StringVar()
        self.priority_var = tk.StringVar(value='中')
        self.due_at_var = tk.StringVar()
        self.reminder_var = tk.StringVar(value='不提醒')
        self.status_var = tk.StringVar(value='准备就绪')
        self.filter_var = tk.StringVar(value='全部')
        self.autostart_var = tk.StringVar()

        self._build_ui()
        self.refresh_autostart_status()
        self.refresh_tasks()
        self.schedule_reminder_check()

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Card.TFrame', background='#1f2937')
        style.configure('Card.TLabel', background='#1f2937', foreground='#f9fafb')
        style.configure('TButton', padding=6)
        style.configure(
            'Treeview',
            rowheight=30,
            fieldbackground='#0f172a',
            background='#0f172a',
            foreground='#e5e7eb',
        )
        style.configure('Treeview.Heading', background='#374151', foreground='#f9fafb')
        style.map('Treeview', background=[('selected', '#2563eb')])

        container = ttk.Frame(self.root, padding=16, style='Card.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        ttk.Label(container, text='桌面悬浮任务列表', style='Card.TLabel', font=('Arial', 16, 'bold')).pack(anchor='w')
        ttk.Label(
            container,
            text='支持 Linux 置顶悬浮、优先级、到期时间、提醒通知与开机自启。',
            style='Card.TLabel',
        ).pack(anchor='w', pady=(4, 12))

        input_frame = ttk.Frame(container, style='Card.TFrame')
        input_frame.pack(fill=tk.X)

        ttk.Entry(input_frame, textvariable=self.title_var).pack(fill=tk.X, pady=(0, 8))

        schedule_frame = ttk.Frame(input_frame, style='Card.TFrame')
        schedule_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(schedule_frame, text='到期时间', style='Card.TLabel').pack(side=tk.LEFT)
        ttk.Entry(schedule_frame, textvariable=self.due_at_var, width=20).pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(schedule_frame, text='格式: YYYY-MM-DD HH:MM', style='Card.TLabel').pack(side=tk.LEFT)

        controls = ttk.Frame(input_frame, style='Card.TFrame')
        controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Combobox(
            controls,
            textvariable=self.priority_var,
            values=['高', '中', '低'],
            state='readonly',
            width=8,
        ).pack(side=tk.LEFT)
        ttk.Combobox(
            controls,
            textvariable=self.reminder_var,
            values=REMINDER_OPTIONS,
            state='readonly',
            width=12,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(controls, text='添加任务', command=self.add_task).pack(side=tk.LEFT)
        ttk.Button(controls, text='切换完成', command=self.toggle_selected).pack(side=tk.LEFT, padx=8)
        ttk.Button(controls, text='重置提醒', command=self.reset_reminder_for_selected).pack(side=tk.LEFT)
        ttk.Button(controls, text='删除任务', command=self.delete_selected).pack(side=tk.RIGHT)

        filter_frame = ttk.Frame(container, style='Card.TFrame')
        filter_frame.pack(fill=tk.X, pady=(4, 10))
        ttk.Label(filter_frame, text='筛选：', style='Card.TLabel').pack(side=tk.LEFT)
        filter_box = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_var,
            values=['全部', '未完成', '已完成'],
            state='readonly',
            width=10,
        )
        filter_box.pack(side=tk.LEFT, padx=(6, 0))
        filter_box.bind('<<ComboboxSelected>>', lambda event: self.refresh_tasks())

        autostart_frame = ttk.Frame(container, style='Card.TFrame')
        autostart_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(autostart_frame, text='启用开机自启', command=self.enable_autostart).pack(side=tk.LEFT)
        ttk.Button(autostart_frame, text='关闭开机自启', command=self.disable_autostart).pack(side=tk.LEFT, padx=8)
        ttk.Label(autostart_frame, textvariable=self.autostart_var, style='Card.TLabel').pack(side=tk.RIGHT)

        legend = ttk.Frame(container, style='Card.TFrame')
        legend.pack(fill=tk.X, pady=(0, 10))
        for label, color in PRIORITY_COLORS.items():
            tk.Label(legend, text=f' {label}优先级 ', bg=color, fg='#111827', padx=6, pady=2).pack(side=tk.LEFT, padx=(0, 6))

        columns = ('status', 'priority', 'due_at', 'reminder', 'title')
        self.tree = ttk.Treeview(container, columns=columns, show='headings', selectmode='browse', height=12)
        self.tree.heading('status', text='状态')
        self.tree.heading('priority', text='优先级')
        self.tree.heading('due_at', text='到期时间')
        self.tree.heading('reminder', text='提醒')
        self.tree.heading('title', text='任务')
        self.tree.column('status', width=80, anchor='center')
        self.tree.column('priority', width=80, anchor='center')
        self.tree.column('due_at', width=150, anchor='center')
        self.tree.column('reminder', width=100, anchor='center')
        self.tree.column('title', width=250, anchor='w')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind('<Double-1>', lambda event: self.toggle_selected())

        self.tree.tag_configure('高', background='#3b1f25')
        self.tree.tag_configure('中', background='#3d3220')
        self.tree.tag_configure('低', background='#12332b')
        self.tree.tag_configure('done', foreground='#9ca3af')
        self.tree.tag_configure('overdue', foreground='#fca5a5')

        footer = ttk.Frame(container, style='Card.TFrame')
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(footer, text='窗口置顶: 开', command=self.toggle_topmost).pack(side=tk.LEFT)
        ttk.Label(footer, textvariable=self.status_var, style='Card.TLabel').pack(side=tk.RIGHT)

    def refresh_autostart_status(self) -> None:
        self.autostart_var.set(f"开机自启：{'已开启' if AUTOSTART_FILE.exists() else '未开启'}")

    def autostart_desktop_entry(self) -> str:
        python_exec = Path(sys.executable).resolve()
        app_path = Path(__file__).resolve()
        return '\n'.join([
            '[Desktop Entry]',
            'Type=Application',
            'Version=1.0',
            'Name=Floating Task List',
            'Comment=Linux floating desktop task list',
            f'Exec={python_exec} {app_path}',
            f'Path={app_path.parent}',
            'Terminal=false',
            'X-GNOME-Autostart-enabled=true',
        ]) + '\n'

    def enable_autostart(self) -> None:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(self.autostart_desktop_entry(), encoding='utf-8')
        self.refresh_autostart_status()
        self.status_var.set('已启用开机自启')

    def disable_autostart(self) -> None:
        if AUTOSTART_FILE.exists():
            AUTOSTART_FILE.unlink()
        self.refresh_autostart_status()
        self.status_var.set('已关闭开机自启')

    def parse_due_at(self, due_at: str) -> str:
        due_at = due_at.strip()
        if not due_at:
            return ''
        try:
            return datetime.strptime(due_at, DATETIME_FORMAT).strftime(DATETIME_FORMAT)
        except ValueError as exc:
            raise ValueError('到期时间格式应为 YYYY-MM-DD HH:MM') from exc

    def add_task(self) -> None:
        title = self.title_var.get().strip()
        priority = self.priority_var.get()
        reminder_label = self.reminder_var.get()
        if not title:
            messagebox.showinfo('提示', '请输入任务内容。')
            return
        try:
            due_at = self.parse_due_at(self.due_at_var.get())
        except ValueError as error:
            messagebox.showerror('时间格式错误', str(error))
            return
        if reminder_label != '不提醒' and not due_at:
            messagebox.showinfo('提示', '设置提醒前请先填写到期时间。')
            return

        self.tasks.append(
            Task(
                title=title,
                priority=priority,
                due_at=due_at,
                reminder_label=reminder_label,
            )
        )
        self.title_var.set('')
        self.due_at_var.set('')
        self.reminder_var.set('不提醒')
        self.status_var.set(f'已添加任务：{title}')
        self.persist_and_refresh()

    def get_selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def get_selected_task(self) -> Task | None:
        index = self.get_selected_index()
        if index is None:
            return None
        tasks = self.filtered_tasks()
        if index >= len(tasks):
            return None
        return tasks[index]

    def delete_selected(self) -> None:
        task = self.get_selected_task()
        if task is None:
            self.status_var.set('请先选择一个任务')
            return
        self.tasks.remove(task)
        self.status_var.set(f'已删除任务：{task.title}')
        self.persist_and_refresh()

    def toggle_selected(self) -> None:
        task = self.get_selected_task()
        if task is None:
            self.status_var.set('请先选择一个任务')
            return
        task.completed = not task.completed
        if not task.completed:
            task.reminded = False
        self.status_var.set(f"任务已{'完成' if task.completed else '恢复'}：{task.title}")
        self.persist_and_refresh()

    def reset_reminder_for_selected(self) -> None:
        task = self.get_selected_task()
        if task is None:
            self.status_var.set('请先选择一个任务')
            return
        task.reminded = False
        self.status_var.set(f'已重置提醒：{task.title}')
        self.persist_and_refresh()

    def filtered_tasks(self) -> List[Task]:
        return [task for task in self.sorted_tasks() if self.matches_filter(task)]

    def sorted_tasks(self) -> List[Task]:
        def sort_key(task: Task) -> tuple:
            due_at = task.due_datetime() or datetime.max
            return (task.completed, PRIORITY_ORDER[task.priority], due_at, task.title.lower())

        return sorted(self.tasks, key=sort_key)

    def matches_filter(self, task: Task) -> bool:
        current_filter = self.filter_var.get()
        if current_filter == '未完成':
            return not task.completed
        if current_filter == '已完成':
            return task.completed
        return True

    def task_status_text(self, task: Task) -> str:
        if task.completed:
            return '已完成'
        due_at = task.due_datetime()
        if due_at and due_at < datetime.now():
            return '已逾期'
        return '进行中'

    def refresh_tasks(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        now = datetime.now()
        for index, task in enumerate(self.filtered_tasks()):
            tags = [task.priority]
            if task.completed:
                tags.append('done')
            elif task.due_datetime() and task.due_datetime() < now:
                tags.append('overdue')
            self.tree.insert(
                '',
                tk.END,
                iid=str(index),
                values=(
                    self.task_status_text(task),
                    task.priority,
                    task.due_at or '-',
                    task.reminder_label,
                    task.title,
                ),
                tags=tuple(tags),
            )
        self.status_var.set(f'当前任务数：{len(self.tasks)}')

    def persist_and_refresh(self) -> None:
        self.store.save(self.tasks)
        self.refresh_tasks()

    def toggle_topmost(self) -> None:
        current = bool(self.root.attributes('-topmost'))
        self.root.attributes('-topmost', not current)
        self.status_var.set(f"窗口置顶：{'开' if not current else '关'}")

    def schedule_reminder_check(self) -> None:
        self.check_reminders()
        self.root.after(30000, self.schedule_reminder_check)

    def check_reminders(self) -> None:
        now = datetime.now()
        pending_notifications: List[str] = []
        changed = False
        for task in self.tasks:
            if task.completed or task.reminded:
                continue
            due_at = task.due_datetime()
            reminder_minutes = task.reminder_minutes()
            if due_at is None or reminder_minutes is None:
                continue
            remind_at = due_at - timedelta(minutes=reminder_minutes)
            if now >= remind_at:
                task.reminded = True
                changed = True
                pending_notifications.append(
                    f'任务：{task.title}\n优先级：{task.priority}\n到期时间：{task.due_at}\n提醒：{task.reminder_label}'
                )
        if changed:
            self.store.save(self.tasks)
            self.refresh_tasks()
        for message in pending_notifications:
            self.root.bell()
            messagebox.showwarning('任务提醒', message)


if __name__ == '__main__':
    root = tk.Tk()
    TaskListApp(root)
    root.mainloop()
