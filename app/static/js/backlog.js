/**
 * Backlog drag-and-drop reordering.
 * Items can be dragged between sprint groups and the backlog.
 */
(function () {
    'use strict';

    var dragItem = null;
    var dragSourceContainer = null;
    var dragPlaceholder = null;

    function init() {
        var containers = document.querySelectorAll('[data-backlog-group]');
        if (!containers.length) return;

        containers.forEach(function (container) {
            container.addEventListener('dragover', onDragOver);
            container.addEventListener('drop', onDrop);
            container.addEventListener('dragleave', onDragLeave);
        });

        initDraggables();
    }

    function initDraggables() {
        document.querySelectorAll('[data-backlog-group] .pp-list-item[data-item-id]').forEach(function (el) {
            el.setAttribute('draggable', 'true');
            el.removeEventListener('dragstart', onDragStart);
            el.removeEventListener('dragend', onDragEnd);
            el.addEventListener('dragstart', onDragStart);
            el.addEventListener('dragend', onDragEnd);
        });
    }

    function onDragStart(e) {
        dragItem = this;
        dragSourceContainer = this.parentNode;
        this.style.opacity = '0.4';
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', this.dataset.itemId);

        dragPlaceholder = document.createElement('div');
        dragPlaceholder.className = 'pp-drag-placeholder';
        dragPlaceholder.style.cssText = 'height:3px; background:var(--pp-primary); border-radius:2px; margin:2px 0;';
    }

    function onDragEnd() {
        this.style.opacity = '';
        if (dragPlaceholder && dragPlaceholder.parentNode) {
            dragPlaceholder.parentNode.removeChild(dragPlaceholder);
        }
        dragItem = null;
        dragSourceContainer = null;
        dragPlaceholder = null;

        document.querySelectorAll('[data-backlog-group]').forEach(function (c) {
            c.classList.remove('pp-drag-over');
        });
    }

    function onDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        var container = e.currentTarget;
        container.classList.add('pp-drag-over');

        var afterElement = getDragAfterElement(container, e.clientY);

        if (dragPlaceholder.parentNode) {
            dragPlaceholder.parentNode.removeChild(dragPlaceholder);
        }

        if (afterElement) {
            container.insertBefore(dragPlaceholder, afterElement);
        } else {
            container.appendChild(dragPlaceholder);
        }
    }

    function onDragLeave(e) {
        if (!e.currentTarget.contains(e.relatedTarget)) {
            e.currentTarget.classList.remove('pp-drag-over');
        }
    }

    function onDrop(e) {
        e.preventDefault();
        if (!dragItem) return;

        var container = e.currentTarget;
        container.classList.remove('pp-drag-over');
        var sprintId = container.dataset.backlogGroup;
        if (sprintId === 'backlog') sprintId = '';

        // Remove empty state from target if present
        var emptyDiv = container.querySelector('.pp-empty');
        if (emptyDiv) emptyDiv.remove();

        var afterElement = getDragAfterElement(container, e.clientY);
        if (afterElement) {
            container.insertBefore(dragItem, afterElement);
        } else {
            container.appendChild(dragItem);
        }

        if (dragPlaceholder && dragPlaceholder.parentNode) {
            dragPlaceholder.parentNode.removeChild(dragPlaceholder);
        }

        // Add empty state to source if it's now empty
        if (dragSourceContainer && dragSourceContainer !== container) {
            var remaining = dragSourceContainer.querySelectorAll('.pp-list-item[data-item-id]');
            if (remaining.length === 0) {
                var empty = document.createElement('div');
                empty.className = 'pp-empty';
                empty.style.padding = '24px';
                empty.innerHTML = '<p style="margin:0; font-size:0.8125rem;">No items.</p>';
                dragSourceContainer.appendChild(empty);
            }
        }

        var siblings = container.querySelectorAll('.pp-list-item[data-item-id]');
        var position = 0;
        for (var i = 0; i < siblings.length; i++) {
            if (siblings[i] === dragItem) {
                position = i;
                break;
            }
        }

        api.post('/backlog/reorder', {
            item_id: parseInt(dragItem.dataset.itemId),
            position: position,
            sprint_id: sprintId ? parseInt(sprintId) : null
        }).catch(function (err) {
            console.error('Reorder failed:', err);
        });
    }

    function getDragAfterElement(container, y) {
        var draggableElements = Array.from(
            container.querySelectorAll('.pp-list-item[data-item-id]:not([style*="opacity"])')
        );

        var closest = null;
        var closestOffset = Number.NEGATIVE_INFINITY;

        draggableElements.forEach(function (child) {
            var box = child.getBoundingClientRect();
            var offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closestOffset) {
                closestOffset = offset;
                closest = child;
            }
        });

        return closest;
    }

    document.addEventListener('DOMContentLoaded', init);
})();
