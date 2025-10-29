import React from "./react@18.3.1/es2022/react.mjs";
import { createRoot } from "./react-dom@18.3.1/es2022/client.mjs";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  useDroppable,
  useSensor,
  useSensors,
  closestCenter,
} from "./@dnd-kit/core@6.0.8/X-ZHJlYWN0LWRvbUAxOC4zLjEscmVhY3RAMTguMy4x/es2022/core.bundle.mjs";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "./@dnd-kit/sortable@10.0.0/X-ZEBkbmQta2l0L2NvcmVANi4wLjgsQGRuZC1raXQvdXRpbGl0aWVzQDMuMi4yLHJlYWN0QDE4LjMuMQ/es2022/sortable.bundle.mjs";
import { CSS } from "./@dnd-kit/utilities@3.2.2/X-ZHJlYWN0QDE4LjMuMQ/es2022/utilities.bundle.mjs";

const { useCallback, useEffect, useMemo, useState } = React;
const h = React.createElement;

const API_BASE = "/api";
const ROOT_ID = "root-dropzone";

const jsonHeaders = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "same-origin",
    ...options,
  });

  if (!response.ok) {
    let detail;
    try {
      detail = await response.json();
    } catch (_error) {
      detail = { detail: response.statusText || "Request failed." };
    }
    const message =
      typeof detail === "object" && detail !== null ? detail.detail ?? JSON.stringify(detail) : String(detail);
    throw new Error(message);
  }

  if (response.status === 204 || response.status === 205) {
    return {};
  }

  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch (_error) {
    throw new Error("Failed to parse server response.");
  }
}

const flattenTasks = (nodes = [], parentId = null, depth = 0, acc = []) => {
  nodes.forEach((task, index) => {
    acc.push({ task, parentId, depth, index });
    flattenTasks(task.children ?? [], task.id, depth + 1, acc);
  });
  return acc;
};

const findTask = (nodes, id, parent = null) => {
  for (let index = 0; index < nodes.length; index += 1) {
    const task = nodes[index];
    if (task.id === id) {
      return { task, parent, index };
    }
    if (task.children?.length) {
      const found = findTask(task.children, id, task);
      if (found) {
        return found;
      }
    }
  }
  return null;
};

const getChildren = (nodes, parentId) => {
  if (parentId === null) {
    return nodes;
  }
  const parent = findTask(nodes, parentId);
  return parent?.task?.children ?? [];
};

const isDescendant = (nodes, ancestorId, candidateId) => {
  const ancestor = findTask(nodes, ancestorId);
  if (!ancestor) {
    return false;
  }
  const stack = [...(ancestor.task.children ?? [])];
  while (stack.length) {
    const item = stack.pop();
    if (item.id === candidateId) {
      return true;
    }
    if (item.children) {
      stack.push(...item.children);
    }
  }
  return false;
};

const pointerCenterY = (event) => {
  const translated = event.active.rect.current?.translated;
  if (translated) {
    return translated.top + translated.height / 2;
  }
  const rect = event.active.rect.current;
  if (rect) {
    return rect.top + rect.height / 2;
  }
  return 0;
};

const DropIntent = {
  Before: "before",
  After: "after",
  Child: "child",
  Root: "root",
};

function TaskPreview({ task }) {
  return h(
    "div",
    { className: "tasks-list" },
    h(
      "div",
      { className: "task-row", style: { cursor: "grabbing" } },
      h("button", { className: "task-delete", "aria-hidden": "true" }),
      h("span", { className: "task-title" }, task.title),
    ),
  );
}

function TaskNode({ task, parentId, dropIndicator, onDelete, renderChildren }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: task.id,
    data: {
      taskId: task.id,
      parentId,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : undefined,
  };

  const dropClasses = [];
  if (dropIndicator?.targetId === task.id) {
    if (dropIndicator.mode === DropIntent.Before) {
      dropClasses.push("drag-over-before");
    } else if (dropIndicator.mode === DropIntent.After) {
      dropClasses.push("drag-over-after");
    } else if (dropIndicator.mode === DropIntent.Child) {
      dropClasses.push("drag-over-child");
    }
  }

  return h(
    "li",
    { ref: setNodeRef, className: dropClasses.join(" ") || undefined, style },
    h(
      "div",
      { className: "task-row", ...attributes, ...listeners },
      h("button", {
        className: "task-delete",
        onClick: () => onDelete(task.id),
        "aria-label": `Delete ${task.title}`,
        type: "button",
      }),
      h("span", { className: "task-title" }, task.title),
    ),
    renderChildren(task),
  );
}

function TaskTree({ tasks, parentId, dropIndicator, onDelete }) {
  if (!tasks.length) {
    return null;
  }
  return h(
    SortableContext,
    { items: tasks.map((task) => task.id), strategy: verticalListSortingStrategy },
    h(
      "ul",
      { className: "tasks-list" },
      ...tasks.map((task) =>
        h(TaskNode, {
          key: task.id,
          task,
          parentId,
          dropIndicator,
          onDelete,
          renderChildren: (node) =>
            h(TaskTree, {
              tasks: node.children ?? [],
              parentId: node.id,
              dropIndicator,
              onDelete,
            }),
        }),
      ),
    ),
  );
}

function RootTaskArea({ tasks, dropIndicator, onDelete }) {
  const { setNodeRef } = useDroppable({
    id: ROOT_ID,
  });
  const isRootTarget = dropIndicator?.mode === DropIntent.Root;
  const classNames = ["tasks-container"];
  if (isRootTarget) {
    classNames.push("root-drop-target");
  }
  return h(
    "div",
    { ref: setNodeRef, className: classNames.join(" ") },
    h(TaskTree, { tasks, parentId: null, dropIndicator, onDelete }),
  );
}

function App() {
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [dropIndicator, setDropIndicator] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 4,
      },
    }),
    useSensor(TouchSensor, { pressDelay: 150 }),
  );

  const flattened = useMemo(() => flattenTasks(tasks), [tasks]);

  const refreshTasks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await request("/tasks");
      setTasks(Array.isArray(data.tasks) ? data.tasks : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshTasks();
  }, [refreshTasks]);

  const handleAddTask = async () => {
    const title = window.prompt("Task title:");
    if (!title || !title.trim()) {
      return;
    }
    try {
      setIsSaving(true);
      await request("/tasks", {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify({ title: title.trim() }),
      });
      await refreshTasks();
    } catch (err) {
      alert(`Failed to create task.\n\n${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (taskId) => {
    const confirmed = window.confirm("Delete this task (and its subtasks)?");
    if (!confirmed) {
      return;
    }
    try {
      setIsSaving(true);
      await request(`/tasks/${encodeURIComponent(taskId)}`, {
        method: "DELETE",
        headers: jsonHeaders,
      });
      await refreshTasks();
    } catch (err) {
      alert(`Failed to delete task.\n\n${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsSaving(false);
    }
  };

  const executeMove = useCallback(
    async (taskId, parentId, position) => {
      const current = findTask(tasks, taskId);
      const currentParentId = current?.parent?.id ?? null;
      const currentIndex = current?.index ?? -1;
      if (currentParentId === parentId && currentIndex === position) {
        return;
      }
      setIsSaving(true);
      try {
        await request("/tasks/move", {
          method: "POST",
          headers: jsonHeaders,
          body: JSON.stringify({
            task_id: taskId,
            parent_id: parentId,
            position,
          }),
        });
        await refreshTasks();
      } catch (err) {
        alert(`Failed to move task.\n\n${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setIsSaving(false);
      }
    },
    [tasks, refreshTasks],
  );

  const handleDragStart = (event) => {
    setActiveId(event.active.id);
    setDropIndicator(null);
  };

  const handleDragOver = (event) => {
    const { over, active } = event;
    if (!over) {
      setDropIndicator(null);
      return;
    }
    if (over.id === ROOT_ID) {
      setDropIndicator({ mode: DropIntent.Root });
      return;
    }
    if (over.id === active.id) {
      setDropIndicator(null);
      return;
    }
    const overData = over.data?.current;
    if (!overData) {
      setDropIndicator(null);
      return;
    }

    const overTaskId = over.id;
    if (isDescendant(tasks, active.id, overTaskId)) {
      setDropIndicator(null);
      return;
    }

    const pointerY = pointerCenterY(event);
    const rect = over.rect;
    const topThreshold = rect.top + rect.height * 0.25;
    const bottomThreshold = rect.bottom - rect.height * 0.25;

    let mode = DropIntent.Child;
    if (pointerY <= topThreshold) {
      mode = DropIntent.Before;
    } else if (pointerY >= bottomThreshold) {
      mode = DropIntent.After;
    }

    setDropIndicator({
      mode,
      targetId: overTaskId,
      parentId: overData.parentId ?? null,
    });
  };

  const handleDragEnd = async (event) => {
    const { active } = event;
    const indicator = dropIndicator;
    setActiveId(null);
    setDropIndicator(null);

    if (!indicator) {
      return;
    }

    if (indicator.mode === DropIntent.Root) {
      const rootChildren = tasks;
      const currentInfo = findTask(tasks, active.id);
      if (currentInfo?.parent === null && currentInfo.index === rootChildren.length - 1) {
        return;
      }
      await executeMove(active.id, null, rootChildren.length);
      return;
    }

    if (!indicator.targetId) {
      return;
    }

    const activeInfo = findTask(tasks, active.id);
    if (!activeInfo) {
      return;
    }

    if (indicator.mode === DropIntent.Child) {
      if (isDescendant(tasks, active.id, indicator.targetId)) {
        return;
      }
      const children = getChildren(tasks, indicator.targetId);
      await executeMove(active.id, indicator.targetId, children.length);
      return;
    }

    const parentId = indicator.parentId ?? null;
    const siblings = getChildren(tasks, parentId);
    const targetIndex = siblings.findIndex((task) => task.id === indicator.targetId);
    if (targetIndex === -1) {
      return;
    }

    let insertIndex = indicator.mode === DropIntent.Before ? targetIndex : targetIndex + 1;

    if (activeInfo.parent?.id === parentId) {
      if (insertIndex > activeInfo.index) {
        insertIndex -= 1;
      }
      if (insertIndex === activeInfo.index) {
        return;
      }
    }

    await executeMove(active.id, parentId, insertIndex);
  };

  const handleDragCancel = () => {
    setActiveId(null);
    setDropIndicator(null);
  };

  const activeTask = useMemo(() => flattened.find((entry) => entry.task.id === activeId)?.task ?? null, [
    flattened,
    activeId,
  ]);

  return h(
    "div",
    { className: "layout" },
    h(
      "aside",
      { className: "sidebar" },
      h(
        "button",
        {
          className: "primary-button",
          type: "button",
          onClick: handleAddTask,
          disabled: isSaving,
        },
        "Add Task",
      ),
      isSaving ? h("span", null, "Saving…") : null,
    ),
    h(
      "main",
      { className: "content", "aria-live": "polite" },
        h(
        "section",
        null,
        isLoading
          ? h("p", { className: "empty-state" }, "Loading tasks…")
          : error
          ? h("p", { className: "empty-state" }, `Failed to load: ${error}`)
          : tasks.length === 0
          ? h("p", { className: "empty-state" }, "No tasks yet. Use “Add Task” to create one.")
          : h(
              DndContext,
              {
                sensors,
                collisionDetection: closestCenter,
                onDragStart: handleDragStart,
                onDragOver: handleDragOver,
                onDragEnd: handleDragEnd,
                onDragCancel: handleDragCancel,
              },
              h(RootTaskArea, { tasks, dropIndicator, onDelete: handleDelete }),
              h(DragOverlay, { adjustScale: false }, activeTask ? h(TaskPreview, { task: activeTask }) : null),
            ),
      ),
    ),
  );
}

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root container not found");
}
const root = createRoot(container);
root.render(h(App));
