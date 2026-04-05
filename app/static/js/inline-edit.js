/**
 * Inline editing for work item detail fields.
 * Supports three modes:
 *   data-inline-edit          — dropdown select (status, priority, type, assignee)
 *   data-inline-edit="text"   — single-line text input (title)
 *   data-inline-edit="textarea" — multi-line textarea (description)
 */
var ppInline = (function () {
    'use strict';

    function sanitizeHtml(html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var scripts = doc.querySelectorAll('script, iframe, object, embed, form');
        scripts.forEach(function (el) { el.remove(); });
        doc.querySelectorAll('*').forEach(function (el) {
            Array.from(el.attributes).forEach(function (attr) {
                if (attr.name.startsWith('on') || (attr.name === 'href' && attr.value.trim().toLowerCase().startsWith('javascript:')) || (attr.name === 'src' && attr.value.trim().toLowerCase().startsWith('javascript:'))) {
                    el.removeAttribute(attr.name);
                }
            });
        });
        return doc.body.innerHTML;
    }

    function renderMarkdown(raw) {
        if (!raw) return '';
        if (typeof marked !== 'undefined' && marked.parse) {
            return sanitizeHtml(marked.parse(raw, { breaks: true }));
        }
        var div = document.createElement('div');
        div.textContent = raw;
        return '<p>' + div.innerHTML.replace(/\n/g, '<br>') + '</p>';
    }

    function init() {
        document.querySelectorAll('[data-inline-edit]').forEach(function (el) {
            var mode = el.dataset.inlineEdit || 'select';
            el.style.cursor = 'pointer';

            if (mode === 'text') {
                el.addEventListener('click', function (e) {
                    if (e.target.tagName === 'INPUT') return;
                    openTextEditor(el);
                });
            } else if (mode === 'textarea') {
                // Render markdown on page load
                var displayEl = el.querySelector('.pp-inline-text-display');
                if (displayEl && el.dataset.currentValue) {
                    displayEl.innerHTML = renderMarkdown(el.dataset.currentValue);
                }
                el.addEventListener('click', function (e) {
                    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'BUTTON') return;
                    openTextareaEditor(el);
                });
            } else {
                el.addEventListener('click', function (e) {
                    e.preventDefault();
                    openDropdown(el);
                });
            }
        });
    }

    /* ---- Text input (title, story_points) ---- */
    function openTextEditor(el) {
        if (el.querySelector('input')) return;
        var field = el.dataset.field;
        var itemId = el.dataset.itemId;
        var currentValue = el.dataset.currentValue || '';
        var displayEl = el.querySelector('.pp-inline-text-display');
        var isNumeric = field === 'story_points';
        var emptyDisplay = el.dataset.emptyDisplay || '';

        var input = document.createElement('input');
        input.type = isNumeric ? 'number' : 'text';
        if (isNumeric) input.min = '0';
        input.className = 'pp-input';
        input.value = currentValue;
        input.style.cssText = 'font-size:inherit; font-weight:inherit; padding:2px 6px; width:100%;';

        if (displayEl) displayEl.style.display = 'none';
        el.appendChild(input);
        input.focus();
        input.select();

        function save() {
            var rawValue = input.value.trim();
            var sendValue = isNumeric ? (rawValue === '' ? null : parseInt(rawValue)) : rawValue;
            if (input.parentNode) input.parentNode.removeChild(input);
            if (displayEl) displayEl.style.display = '';

            if ((!isNumeric && !rawValue) || rawValue === currentValue) return;
            if (isNumeric && String(sendValue) === currentValue) return;

            var data = {};
            data[field] = sendValue;
            api.patch('/api/items/' + itemId, data).then(function (res) {
                if (res.ok) {
                    el.dataset.currentValue = rawValue;
                    if (displayEl) displayEl.textContent = rawValue || emptyDisplay;
                }
            }).catch(function (err) {
                console.error('Inline text edit failed:', err);
            });
        }

        input.addEventListener('blur', save);
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
            if (e.key === 'Escape') {
                input.value = currentValue;
                input.blur();
            }
        });
    }

    /* ---- Textarea (description) ---- */
    function openTextareaEditor(el) {
        if (el.querySelector('textarea')) return;
        var field = el.dataset.field;
        var itemId = el.dataset.itemId;
        var currentValue = el.dataset.currentValue || '';
        var displayEl = el.querySelector('.pp-inline-text-display');
        var placeholder = el.querySelector('.pp-inline-placeholder');

        var textarea = document.createElement('textarea');
        textarea.className = 'pp-input';
        textarea.value = currentValue;
        textarea.rows = 4;
        textarea.style.cssText = 'font-size:0.875rem; width:100%; resize:vertical; min-height:80px;';
        textarea.addEventListener('click', function (e) { e.stopPropagation(); });

        var actions = document.createElement('div');
        actions.style.cssText = 'display:flex; gap:6px; margin-top:6px;';
        var saveBtn = document.createElement('button');
        saveBtn.className = 'pp-btn pp-btn-primary pp-btn-sm';
        saveBtn.textContent = 'Save';
        var cancelBtn = document.createElement('button');
        cancelBtn.className = 'pp-btn pp-btn-secondary pp-btn-sm';
        cancelBtn.textContent = 'Cancel';
        actions.appendChild(saveBtn);
        actions.appendChild(cancelBtn);

        if (displayEl) displayEl.style.display = 'none';
        if (placeholder) placeholder.style.display = 'none';
        el.appendChild(textarea);
        el.appendChild(actions);
        textarea.focus();

        function close(newValue) {
            if (textarea.parentNode) textarea.parentNode.removeChild(textarea);
            if (actions.parentNode) actions.parentNode.removeChild(actions);
            var val = newValue !== undefined ? newValue : el.dataset.currentValue;
            if (displayEl) {
                displayEl.innerHTML = renderMarkdown(val);
                displayEl.style.display = val ? '' : 'none';
            }
            if (placeholder) {
                placeholder.style.display = val ? 'none' : '';
            }
        }

        saveBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            var newValue = textarea.value.trim();
            var oldValue = currentValue;
            el.dataset.currentValue = newValue;
            close(newValue);

            if (newValue !== oldValue) {
                var data = {};
                data[field] = newValue;
                api.patch('/api/items/' + itemId, data).catch(function (err) {
                    console.error('Inline textarea edit failed:', err);
                    el.dataset.currentValue = oldValue;
                    if (displayEl) {
                        displayEl.innerHTML = renderMarkdown(oldValue);
                        displayEl.style.display = oldValue ? '' : 'none';
                    }
                    if (placeholder) {
                        placeholder.style.display = oldValue ? 'none' : '';
                    }
                });
            }
        });

        cancelBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            close();
        });

        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { e.stopPropagation(); close(); }
        });
    }

    /* ---- Dropdown (status, priority, type, assignee) ---- */
    function openDropdown(el) {
        if (el.querySelector('.pp-inline-dropdown')) return;

        var field = el.dataset.field;
        var itemId = el.dataset.itemId;
        var options = JSON.parse(el.dataset.options || '[]');
        var currentValue = el.dataset.currentValue || '';

        var dropdown = document.createElement('div');
        dropdown.className = 'pp-inline-dropdown';
        dropdown.style.cssText = 'position:absolute; z-index:100; background:var(--pp-surface); border:1px solid var(--pp-border); border-radius:var(--pp-radius); box-shadow:var(--pp-shadow-lg); min-width:160px; max-height:240px; overflow-y:auto; padding:4px 0;';

        options.forEach(function (opt) {
            var item = document.createElement('div');
            item.className = 'pp-inline-option';
            item.style.cssText = 'padding:6px 12px; font-size:0.8125rem; cursor:pointer; display:flex; align-items:center; gap:6px;';

            var isSelected = String(opt.value) === String(currentValue);
            if (isSelected) {
                item.style.background = 'var(--pp-primary-subtle)';
                item.style.fontWeight = '600';
            }

            if (opt.color) {
                var dot = document.createElement('span');
                dot.style.cssText = 'width:8px; height:8px; border-radius:50%; background:' + opt.color + '; flex-shrink:0;';
                item.appendChild(dot);
            }
            if (opt.icon) {
                var icon = document.createElement('i');
                icon.className = opt.icon;
                icon.style.cssText = 'font-size:0.8125rem;';
                if (opt.color) icon.style.color = opt.color;
                item.appendChild(icon);
            }

            var label = document.createElement('span');
            label.textContent = opt.label;
            item.appendChild(label);

            item.addEventListener('click', function (e) {
                e.stopPropagation();
                selectOption(el, itemId, field, opt);
                closeOverlay(dropdown, backdrop);
            });

            item.addEventListener('mouseenter', function () {
                if (!isSelected) item.style.background = 'var(--pp-surface-hover)';
            });
            item.addEventListener('mouseleave', function () {
                item.style.background = isSelected ? 'var(--pp-primary-subtle)' : '';
            });

            dropdown.appendChild(item);
        });

        el.style.position = 'relative';
        el.appendChild(dropdown);

        var backdrop = document.createElement('div');
        backdrop.style.cssText = 'position:fixed; inset:0; z-index:99;';
        backdrop.addEventListener('click', function () {
            closeOverlay(dropdown, backdrop);
        });
        document.body.appendChild(backdrop);
    }

    function closeOverlay(dropdown, backdrop) {
        if (dropdown.parentNode) dropdown.parentNode.removeChild(dropdown);
        if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
    }

    function selectOption(el, itemId, field, opt) {
        var data = {};
        data[field] = opt.value;

        api.patch('/api/items/' + itemId, data).then(function (res) {
            if (res.ok) {
                updateDisplay(el, field, opt, res.item);
            }
        }).catch(function (err) {
            console.error('Inline edit failed:', err);
        });
    }

    function updateDisplay(el, field, opt, item) {
        el.dataset.currentValue = String(opt.value);

        var displayEl = el.querySelector('.pp-inline-value');
        if (!displayEl) displayEl = el;

        if (field === 'status_id') {
            var dot = displayEl.querySelector('.pp-status-dot');
            if (dot) dot.style.background = opt.color;
            var text = displayEl.querySelector('.pp-inline-text');
            if (text) text.textContent = opt.label;
        } else if (field === 'priority') {
            var icon = displayEl.querySelector('i');
            if (icon && item) {
                icon.className = item.priority_icon || '';
                icon.style.color = item.priority_color || '';
            }
            var text = displayEl.querySelector('.pp-inline-text');
            if (text) text.textContent = opt.label;
        } else if (field === 'assignee_id') {
            var text = displayEl.querySelector('.pp-inline-text');
            if (text) text.textContent = opt.label;
        } else if (field === 'item_type_id') {
            var icon = displayEl.querySelector('i');
            if (icon) {
                icon.className = opt.icon || '';
                icon.style.color = opt.color || '';
            }
            var text = displayEl.querySelector('.pp-inline-text');
            if (text) text.textContent = opt.label;
        }
    }

    return { init: init };
})();

/**
 * AJAX comments — intercept form submit and delete buttons.
 */
var ppComments = (function () {
    'use strict';

    function init(itemId, projectKey, itemKey) {
        var form = document.getElementById('comment-form');
        if (!form) return;

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var textarea = form.querySelector('textarea[name="body"]');
            var body = textarea.value.trim();
            if (!body) return;

            var btn = form.querySelector('button[type="submit"]');
            btn.disabled = true;

            api.post('/api/items/' + itemId + '/comments', { body: body }).then(function (res) {
                if (res.ok) {
                    appendComment(res.comment, itemId, projectKey, itemKey);
                    textarea.value = '';
                    var emptyMsg = document.getElementById('no-comments-msg');
                    if (emptyMsg) emptyMsg.remove();
                }
            }).catch(function (err) {
                console.error('Comment failed:', err);
            }).finally(function () {
                btn.disabled = false;
            });
        });

        document.getElementById('comments-list').addEventListener('click', function (e) {
            var btn = e.target.closest('[data-delete-comment]');
            if (!btn) return;
            e.preventDefault();
            if (!confirm('Delete this comment?')) return;

            var commentId = btn.dataset.deleteComment;
            api.del('/api/items/' + itemId + '/comments/' + commentId).then(function (res) {
                if (res.ok) {
                    var el = document.getElementById('comment-' + commentId);
                    if (el) el.remove();
                }
            }).catch(function (err) {
                console.error('Delete comment failed:', err);
            });
        });
    }

    function appendComment(comment, itemId, projectKey, itemKey) {
        var list = document.getElementById('comments-list');
        var div = document.createElement('div');
        div.className = 'pp-comment';
        div.id = 'comment-' + comment.id;

        var deleteBtn = comment.is_mine
            ? '<button data-delete-comment="' + comment.id + '" class="pp-btn pp-btn-ghost pp-btn-sm" style="padding:2px 6px; color:var(--pp-danger);" title="Delete"><i class="bi bi-trash" style="font-size:0.75rem;"></i></button>'
            : '';

        div.innerHTML =
            '<div class="pp-comment-header">' +
                '<strong style="font-size:0.8125rem;">' + escapeHtml(comment.author) + '</strong>' +
                '<div class="d-flex align-items-center gap-2">' +
                    '<span style="color:var(--pp-text-muted); font-size:0.75rem;">' + escapeHtml(comment.created_at) + '</span>' +
                    deleteBtn +
                '</div>' +
            '</div>' +
            '<p style="margin:0; white-space:pre-wrap; font-size:0.8125rem;">' + escapeHtml(comment.body) + '</p>';

        list.appendChild(div);
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { init: init };
})();

document.addEventListener('DOMContentLoaded', function () {
    ppInline.init();
});
