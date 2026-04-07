document.addEventListener('DOMContentLoaded', function () {
    var draggedCard = null;
    var csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (!csrfToken) {
        var hidden = document.querySelector('input[name="csrf_token"]');
        csrfToken = hidden ? hidden.value : '';
    } else {
        csrfToken = csrfToken.content;
    }

    document.querySelectorAll('.kanban-card').forEach(function (card) {
        card.addEventListener('dragstart', function (e) {
            draggedCard = card;
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.itemId);
        });

        card.addEventListener('dragend', function () {
            card.classList.remove('dragging');
            draggedCard = null;
            document.querySelectorAll('.drop-zone-active').forEach(function (el) {
                el.classList.remove('drop-zone-active');
            });
        });

        card.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                var tag = e.target.tagName;
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'BUTTON' || e.target.closest('[data-sp-edit]')) return;
                var link = card.querySelector('a');
                if (link) link.click();
            }
        });
    });

    document.querySelectorAll('.kanban-column-body').forEach(function (col) {
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

            col.appendChild(draggedCard);

            var itemId = draggedCard.dataset.itemId;
            var statusId = col.dataset.statusId;
            var cards = col.querySelectorAll('.kanban-card');
            var position = Array.prototype.indexOf.call(cards, draggedCard);

            fetch('/board/move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    item_id: parseInt(itemId),
                    status_id: parseInt(statusId),
                    position: position
                })
            }).then(function (res) {
                if (!res.ok) {
                    location.reload();
                } else {
                    updateColumnCounts();
                }
            }).catch(function () {
                location.reload();
            });
        });
    });

    function updateColumnCounts() {
        document.querySelectorAll('.kanban-column').forEach(function (col) {
            var body = col.querySelector('.kanban-column-body');
            var badge = col.querySelector('.kanban-column-header .pp-badge');
            if (body && badge) {
                badge.textContent = body.querySelectorAll('.kanban-card').length;
            }
        });
    }

    // Touch support for mobile drag-and-drop
    var touchCard = null;
    var touchClone = null;
    var touchStartX, touchStartY;

    document.querySelectorAll('.kanban-card').forEach(function (card) {
        card.addEventListener('touchstart', function (e) {
            if (e.touches.length !== 1) return;
            touchCard = card;
            var touch = e.touches[0];
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
        }, { passive: true });
    });

    document.addEventListener('touchmove', function (e) {
        if (!touchCard) return;
        var touch = e.touches[0];
        var dx = Math.abs(touch.clientX - touchStartX);
        var dy = Math.abs(touch.clientY - touchStartY);

        if (dx > 10 || dy > 10) {
            if (!touchClone) {
                touchClone = touchCard.cloneNode(true);
                touchClone.style.position = 'fixed';
                touchClone.style.zIndex = '9999';
                touchClone.style.opacity = '0.8';
                touchClone.style.width = touchCard.offsetWidth + 'px';
                touchClone.style.pointerEvents = 'none';
                document.body.appendChild(touchClone);
                touchCard.style.opacity = '0.3';
            }
            touchClone.style.left = (touch.clientX - 50) + 'px';
            touchClone.style.top = (touch.clientY - 20) + 'px';
            e.preventDefault();
        }
    }, { passive: false });

    document.addEventListener('touchend', function (e) {
        if (!touchCard || !touchClone) {
            touchCard = null;
            return;
        }

        document.body.removeChild(touchClone);
        touchCard.style.opacity = '';

        var touch = e.changedTouches[0];
        var dropTarget = document.elementFromPoint(touch.clientX, touch.clientY);
        var targetCol = dropTarget ? dropTarget.closest('.kanban-column-body') : null;

        if (targetCol) {
            targetCol.appendChild(touchCard);

            var itemId = touchCard.dataset.itemId;
            var statusId = targetCol.dataset.statusId;
            var cards = targetCol.querySelectorAll('.kanban-card');
            var position = Array.prototype.indexOf.call(cards, touchCard);

            fetch('/board/move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    item_id: parseInt(itemId),
                    status_id: parseInt(statusId),
                    position: position
                })
            }).then(function (res) {
                if (!res.ok) location.reload();
                else updateColumnCounts();
            }).catch(function () {
                location.reload();
            });
        }

        touchCard = null;
        touchClone = null;
    });
});
