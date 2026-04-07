/**
 * Drag-and-drop for epic board (epic cards between status columns).
 */
(function () {
    'use strict';

    var draggedCard = null;

    document.addEventListener('dragstart', function (e) {
        var card = e.target.closest('.epic-card');
        if (!card) return;
        draggedCard = card;
        card.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', card.dataset.epicId);
    });

    document.addEventListener('dragend', function (e) {
        if (draggedCard) {
            draggedCard.classList.remove('dragging');
            draggedCard = null;
        }
        document.querySelectorAll('.drop-zone-active').forEach(function (el) {
            el.classList.remove('drop-zone-active');
        });
    });

    document.querySelectorAll('.kanban-column-body[data-epic-status]').forEach(function (col) {
        col.addEventListener('dragover', function (e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            col.classList.add('drop-zone-active');
        });

        col.addEventListener('dragleave', function (e) {
            if (!col.contains(e.relatedTarget)) {
                col.classList.remove('drop-zone-active');
            }
        });

        col.addEventListener('drop', function (e) {
            e.preventDefault();
            col.classList.remove('drop-zone-active');
            if (!draggedCard) return;

            var epicId = draggedCard.dataset.epicId;
            var newStatus = col.dataset.epicStatus;

            col.appendChild(draggedCard);

            api.patch('/api/epics/' + epicId, { status: newStatus }).catch(function (err) {
                console.error('Epic status update failed:', err);
                location.reload();
            });
        });
    });

    // Touch support
    var touchCard = null;
    var touchClone = null;

    document.addEventListener('touchstart', function (e) {
        var card = e.target.closest('.epic-card');
        if (!card) return;
        touchCard = card;
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (!touchCard) return;
        e.preventDefault();

        if (!touchClone) {
            touchClone = touchCard.cloneNode(true);
            touchClone.style.cssText = 'position:fixed; z-index:1000; pointer-events:none; opacity:0.8; width:' + touchCard.offsetWidth + 'px;';
            document.body.appendChild(touchClone);
            touchCard.style.opacity = '0.3';
        }

        var touch = e.touches[0];
        touchClone.style.left = touch.clientX - 20 + 'px';
        touchClone.style.top = touch.clientY - 20 + 'px';
    }, { passive: false });

    document.addEventListener('touchend', function (e) {
        if (!touchCard) return;

        if (touchClone) {
            var touch = e.changedTouches[0];
            touchClone.remove();
            touchClone = null;
            touchCard.style.opacity = '';

            var target = document.elementFromPoint(touch.clientX, touch.clientY);
            var col = target ? target.closest('.kanban-column-body[data-epic-status]') : null;

            if (col) {
                var epicId = touchCard.dataset.epicId;
                var newStatus = col.dataset.epicStatus;
                col.appendChild(touchCard);
                api.patch('/api/epics/' + epicId, { status: newStatus }).catch(function () {
                    location.reload();
                });
            }
        }

        touchCard = null;
    });
})();
