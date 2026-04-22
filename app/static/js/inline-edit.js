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

            if (mode === 'date') {
                el.addEventListener('click', function (e) {
                    if (e.target.tagName === 'INPUT') return;
                    openDateEditor(el);
                });
            } else if (mode === 'text') {
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

    /* ---- Date input (due_date) ---- */
    function openDateEditor(el) {
        if (el.querySelector('input')) return;
        var field = el.dataset.field;
        var itemId = el.dataset.itemId;
        var currentValue = el.dataset.currentValue || '';
        var displayEl = el.querySelector('.pp-inline-text-display');

        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex; gap:4px; align-items:center;';

        var input = document.createElement('input');
        input.type = 'date';
        input.className = 'pp-input';
        input.value = currentValue;
        input.style.cssText = 'font-size:0.8125rem; padding:2px 6px; min-height:32px;';

        var clearBtn = document.createElement('button');
        clearBtn.className = 'pp-btn pp-btn-ghost pp-btn-sm';
        clearBtn.textContent = 'Clear';
        clearBtn.style.cssText = 'font-size:0.6875rem; padding:2px 6px;';
        clearBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            input.value = '';
            save();
        });

        wrap.appendChild(input);
        wrap.appendChild(clearBtn);

        if (displayEl) displayEl.style.display = 'none';
        el.appendChild(wrap);
        input.focus();

        function save() {
            var newValue = input.value;
            if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
            if (displayEl) displayEl.style.display = '';

            if (newValue === currentValue) return;

            var data = {};
            data[field] = newValue || null;
            api.patch('/api/items/' + itemId, data).then(function (res) {
                if (res.ok) {
                    el.dataset.currentValue = newValue;
                    if (displayEl) {
                        if (newValue) {
                            var d = new Date(newValue + 'T00:00:00');
                            var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                            displayEl.textContent = months[d.getMonth()] + ' ' + String(d.getDate()).padStart(2, '0') + ', ' + d.getFullYear();
                            var today = new Date(); today.setHours(0,0,0,0);
                            displayEl.classList.toggle('pp-overdue', d < today);
                        } else {
                            displayEl.textContent = '\u2014';
                            displayEl.classList.remove('pp-overdue');
                        }
                    }
                }
            }).catch(function (err) {
                console.error('Inline date edit failed:', err);
            });
        }

        input.addEventListener('change', save);
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                input.value = currentValue;
                if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
                if (displayEl) displayEl.style.display = '';
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
        } else if (field === 'sprint_id') {
            var text = displayEl.querySelector('.pp-inline-text');
            if (text) text.textContent = opt.label;
        }
    }

    return { init: init };
})();

/**
 * AJAX comments with markdown rendering and @mention support.
 */
var ppComments = (function () {
    'use strict';

    var _members = null;
    var _projectKey = null;
    var _mentionState = null; // { start, selectedIndex }

    function renderCommentMarkdown(raw) {
        if (!raw) return '';
        var html;
        if (typeof marked !== 'undefined' && marked.parse) {
            html = sanitizeHtml(marked.parse(raw, { breaks: true }));
        } else {
            var div = document.createElement('div');
            div.textContent = raw;
            html = '<p>' + div.innerHTML.replace(/\n/g, '<br>') + '</p>';
        }
        // Replace @mentions with profile links
        html = html.replace(/@([\w.\-]+)/g, function (match, name) {
            var displayName = name.replace(/\./g, ' ');
            var member = _members ? _members.find(function (m) {
                return m.name.replace(/\s+/g, '.').toLowerCase() === name.toLowerCase()
                    || m.name.toLowerCase() === displayName.toLowerCase();
            }) : null;
            var href = member ? '/users/' + member.id : '#';
            return '<a class="pp-mention" href="' + href + '" title="' + displayName + '">@' + displayName + '</a>';
        });
        return html;
    }

    function sanitizeHtml(html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        doc.querySelectorAll('script, iframe, object, embed, form').forEach(function (el) { el.remove(); });
        doc.querySelectorAll('*').forEach(function (el) {
            Array.from(el.attributes).forEach(function (attr) {
                if (attr.name.startsWith('on') || (attr.name === 'href' && attr.value.trim().toLowerCase().startsWith('javascript:')) || (attr.name === 'src' && attr.value.trim().toLowerCase().startsWith('javascript:'))) {
                    el.removeAttribute(attr.name);
                }
            });
        });
        return doc.body.innerHTML;
    }

    function loadMembers(projectKey, callback) {
        if (_members) { callback(_members); return; }
        api.get('/api/projects/' + projectKey + '/form-options').then(function (data) {
            _members = data.members;
            callback(_members);
        });
    }

    function init(itemId, projectKey, itemKey) {
        _projectKey = projectKey;
        var form = document.getElementById('comment-form');
        if (!form) return;

        // Load members first, then render existing comments with proper profile links
        loadMembers(projectKey, function () {
            document.querySelectorAll('.pp-comment-body[data-raw-body]').forEach(function (el) {
                el.innerHTML = renderCommentMarkdown(el.dataset.rawBody);
            });
        });

        // Write/Preview tabs
        var tabs = form.querySelectorAll('[data-comment-tab]');
        var textarea = form.querySelector('textarea[name="body"]');
        var preview = document.getElementById('comment-preview');

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function (e) {
                e.preventDefault();
                tabs.forEach(function (t) { t.classList.remove('active'); });
                tab.classList.add('active');
                if (tab.dataset.commentTab === 'preview') {
                    var raw = textarea.value.trim();
                    preview.innerHTML = raw ? renderCommentMarkdown(raw) : 'Nothing to preview';
                    preview.className = 'pp-comment-preview' + (raw ? ' pp-markdown' : '');
                    textarea.style.display = 'none';
                    preview.style.display = '';
                } else {
                    textarea.style.display = '';
                    preview.style.display = 'none';
                    textarea.focus();
                }
            });
        });

        // @mention autocomplete
        var mentionDropdown = document.getElementById('mention-dropdown');
        initMentions(textarea, mentionDropdown, projectKey);

        // Submit
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var body = textarea.value.trim();
            if (!body) return;

            var btn = form.querySelector('button[type="submit"]');
            btn.disabled = true;

            api.post('/api/items/' + itemId + '/comments', { body: body }).then(function (res) {
                if (res.ok) {
                    appendComment(res.comment);
                    textarea.value = '';
                    // Switch back to write tab
                    tabs.forEach(function (t) {
                        t.classList.toggle('active', t.dataset.commentTab === 'write');
                    });
                    textarea.style.display = '';
                    preview.style.display = 'none';
                    var emptyMsg = document.getElementById('no-comments-msg');
                    if (emptyMsg) emptyMsg.remove();
                }
            }).catch(function (err) {
                console.error('Comment failed:', err);
            }).finally(function () {
                btn.disabled = false;
            });
        });

        // Delete
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

    function initMentions(textarea, dropdown, projectKey) {
        textarea.addEventListener('input', function () {
            var pos = textarea.selectionStart;
            var text = textarea.value.substring(0, pos);
            // Find the @ trigger: must be at start of line/string or after whitespace
            var match = text.match(/(^|[\s])@([\w.\-]*)$/);
            if (!match) {
                closeMentions(dropdown);
                return;
            }
            var query = match[2].toLowerCase();
            _mentionState = { start: pos - match[2].length - 1, selectedIndex: 0 };

            loadMembers(projectKey, function (members) {
                var filtered = members.filter(function (m) {
                    return m.name.toLowerCase().indexOf(query) !== -1;
                });
                if (!filtered.length) {
                    closeMentions(dropdown);
                    return;
                }
                _mentionState.selectedIndex = 0;
                renderMentionDropdown(dropdown, filtered, textarea);
            });
        });

        textarea.addEventListener('keydown', function (e) {
            if (!_mentionState || dropdown.style.display === 'none') return;
            var options = dropdown.querySelectorAll('.pp-mention-option');
            if (!options.length) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                _mentionState.selectedIndex = Math.min(_mentionState.selectedIndex + 1, options.length - 1);
                updateMentionSelection(options);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                _mentionState.selectedIndex = Math.max(_mentionState.selectedIndex - 1, 0);
                updateMentionSelection(options);
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                if (dropdown.style.display !== 'none') {
                    e.preventDefault();
                    e.stopPropagation();
                    var selected = options[_mentionState.selectedIndex];
                    if (selected) insertMention(textarea, selected.dataset.memberName, dropdown);
                }
            } else if (e.key === 'Escape') {
                closeMentions(dropdown);
            }
        });

        textarea.addEventListener('blur', function () {
            setTimeout(function () { closeMentions(dropdown); }, 200);
        });
    }

    function renderMentionDropdown(dropdown, members, textarea) {
        dropdown.innerHTML = '';
        members.forEach(function (m, i) {
            var opt = document.createElement('div');
            opt.className = 'pp-mention-option' + (i === 0 ? ' selected' : '');
            opt.dataset.memberName = m.name;
            opt.innerHTML = '<span class="pp-mention-avatar">' + escapeHtml(m.name.substring(0, 2)) + '</span>' +
                '<span>' + escapeHtml(m.name) + '</span>';
            opt.addEventListener('mousedown', function (e) {
                e.preventDefault();
                insertMention(textarea, m.name, dropdown);
            });
            dropdown.appendChild(opt);
        });
        // Position below caret
        positionMentionDropdown(dropdown, textarea);
        dropdown.style.display = '';
    }

    function positionMentionDropdown(dropdown, textarea) {
        var rect = textarea.getBoundingClientRect();
        dropdown.style.position = 'absolute';
        dropdown.style.left = '0';
        dropdown.style.bottom = (textarea.offsetHeight + 4) + 'px';
    }

    function updateMentionSelection(options) {
        options.forEach(function (o, i) {
            o.classList.toggle('selected', i === _mentionState.selectedIndex);
        });
    }

    function insertMention(textarea, name, dropdown) {
        if (!_mentionState) return;
        var before = textarea.value.substring(0, _mentionState.start);
        var after = textarea.value.substring(textarea.selectionStart);
        // Use display name with dots/hyphens preserved, replace spaces with dots for mention token
        var mentionName = name.replace(/\s+/g, '.');
        textarea.value = before + '@' + mentionName + ' ' + after;
        var newPos = _mentionState.start + 1 + mentionName.length + 1;
        textarea.selectionStart = textarea.selectionEnd = newPos;
        closeMentions(dropdown);
        textarea.focus();
    }

    function closeMentions(dropdown) {
        dropdown.style.display = 'none';
        _mentionState = null;
    }

    function appendComment(comment) {
        var list = document.getElementById('comments-list');
        var div = document.createElement('div');
        div.className = 'pp-comment';
        div.id = 'comment-' + comment.id;

        var initials = escapeHtml(comment.author.substring(0, 2));
        var deleteBtn = comment.is_mine
            ? '<button data-delete-comment="' + comment.id + '" class="pp-btn pp-btn-ghost pp-btn-sm" style="padding:2px 4px; color:var(--pp-danger); margin-left:auto;" title="Delete"><i class="bi bi-trash" style="font-size:0.6875rem;"></i></button>'
            : '';

        div.innerHTML =
            '<div class="pp-comment-avatar">' + initials + '</div>' +
            '<div class="pp-comment-content">' +
                '<div class="pp-comment-header">' +
                    '<span class="pp-comment-author">' + escapeHtml(comment.author) + '</span>' +
                    '<span class="pp-comment-time">' + escapeHtml(comment.created_at) + '</span>' +
                    deleteBtn +
                '</div>' +
                '<div class="pp-comment-body pp-markdown">' + renderCommentMarkdown(comment.body) + '</div>' +
            '</div>';

        list.insertBefore(div, list.firstChild);
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { init: init };
})();

/**
 * Label picker for work item detail page.
 */
var ppLabels = (function () {
    'use strict';

    var _backdrop = null;

    function toggle() {
        var dd = document.getElementById('label-dropdown');
        if (!dd) return;
        var isOpen = dd.style.display !== 'none' && dd.parentNode === document.body;
        if (isOpen) {
            _close();
            return;
        }
        var btn = document.getElementById('add-label-btn');
        var rect = btn.getBoundingClientRect();
        dd.style.position = 'fixed';
        dd.style.zIndex = '1100';
        dd.style.display = '';
        // Move to body so it's not clipped
        document.body.appendChild(dd);
        // Position below the button, left-aligned
        var top = rect.bottom + 2;
        var left = rect.left;
        // Keep on screen
        if (left + 200 > window.innerWidth) left = window.innerWidth - 210;
        if (left < 8) left = 8;
        if (top + 240 > window.innerHeight) top = rect.top - 240;
        if (top < 8) top = 8;
        dd.style.top = top + 'px';
        dd.style.left = left + 'px';
        dd.style.minWidth = '200px';

        _backdrop = document.createElement('div');
        _backdrop.style.cssText = 'position:fixed; inset:0; z-index:1099;';
        _backdrop.addEventListener('click', _close);
        document.body.appendChild(_backdrop);
    }

    function _close() {
        var dd = document.getElementById('label-dropdown');
        if (dd) {
            dd.style.display = 'none';
            // Move back to its original parent so template references still work
            var picker = document.querySelector('.pp-label-picker');
            if (picker && dd.parentNode !== picker) picker.appendChild(dd);
        }
        if (_backdrop && _backdrop.parentNode) {
            _backdrop.parentNode.removeChild(_backdrop);
            _backdrop = null;
        }
    }

    function add(itemId, labelId, name, color, btn) {
        api.post('/api/items/' + itemId + '/labels', { label_id: labelId }).then(function (res) {
            if (res.ok) {
                var container = document.getElementById('item-labels');
                var span = document.createElement('span');
                span.className = 'pp-label-badge';
                span.style.cssText = 'background:' + color + '; color:#fff;';
                span.dataset.labelId = labelId;
                span.innerHTML = escapeHtml(name) +
                    ' <button class="pp-label-remove" onclick="ppLabels.remove(' + itemId + ', ' + labelId + ', this)" title="Remove">&times;</button>';
                container.appendChild(span);
                // Hide the option
                if (btn) btn.style.display = 'none';
                toggle();
            }
        }).catch(function (err) {
            console.error('Add label failed:', err);
        });
    }

    function remove(itemId, labelId, btn) {
        api.del('/api/items/' + itemId + '/labels/' + labelId).then(function (res) {
            if (res.ok) {
                var badge = btn.closest('.pp-label-badge');
                if (badge) badge.remove();
                // Re-show the option in dropdown
                var dd = document.getElementById('label-dropdown');
                if (dd) {
                    var opt = dd.querySelector('[data-label-id="' + labelId + '"]');
                    if (opt) opt.style.display = '';
                }
            }
        }).catch(function (err) {
            console.error('Remove label failed:', err);
        });
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function create(itemId, projectKey) {
        var nameInput = document.getElementById('new-label-name');
        var colorInput = document.getElementById('new-label-color');
        var name = nameInput.value.trim();
        if (!name) return;

        api.post('/api/projects/' + projectKey + '/labels', {
            name: name,
            color: colorInput.value
        }).then(function (res) {
            if (res.ok) {
                var label = res.label;
                // Add the new label option to the dropdown
                var dd = document.getElementById('label-dropdown');
                var createSection = dd.querySelector('.pp-label-create');
                var btn = document.createElement('button');
                btn.className = 'pp-label-option';
                btn.setAttribute('onclick', 'ppLabels.add(' + itemId + ', ' + label.id + ', \'' + escapeHtml(label.name).replace(/'/g, "\\'") + '\', \'' + label.color + '\', this)');
                btn.dataset.labelId = label.id;
                btn.innerHTML = '<span class="pp-label-dot" style="background:' + label.color + ';"></span> ' + escapeHtml(label.name);
                dd.insertBefore(btn, createSection);

                // Immediately add it to the item too
                nameInput.value = '';
                add(itemId, label.id, label.name, label.color, btn);
            }
        }).catch(function (err) {
            console.error('Create label failed:', err);
        });
    }

    return { toggle: toggle, add: add, remove: remove, create: create };
})();

document.addEventListener('DOMContentLoaded', function () {
    ppInline.init();
});
