var ppModal = {
    _instance: null,

    _escHtml: function (str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    _escAttr: function (str) {
        return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },

    _el: function () {
        return document.getElementById('globalModal');
    },

    _getInstance: function () {
        if (!this._instance) {
            this._instance = new bootstrap.Modal(this._el());
        }
        return this._instance;
    },

    show: function (opts) {
        var el = this._el();
        document.getElementById('globalModalTitle').textContent = opts.title || '';
        document.getElementById('globalModalBody').innerHTML = opts.body || '';
        var submitBtn = document.getElementById('globalModalSubmit');
        submitBtn.textContent = opts.submitLabel || 'Create';

        // Remove old listener
        var newBtn = submitBtn.cloneNode(true);
        submitBtn.parentNode.replaceChild(newBtn, submitBtn);

        if (opts.onSubmit) {
            newBtn.addEventListener('click', function () {
                newBtn.disabled = true;
                newBtn.textContent = 'Saving...';
                var result = opts.onSubmit();
                if (result && result.then) {
                    result.then(function () {
                        ppModal.close();
                        if (opts.onSuccess) opts.onSuccess();
                    }).catch(function (err) {
                        newBtn.disabled = false;
                        newBtn.textContent = opts.submitLabel || 'Create';
                        ppModal.showError(err.message || 'Something went wrong');
                    });
                }
            });
        }

        this._getInstance().show();

        // Focus first input
        el.addEventListener('shown.bs.modal', function handler() {
            var firstInput = el.querySelector('input:not([type=hidden]), textarea, select');
            if (firstInput) firstInput.focus();
            el.removeEventListener('shown.bs.modal', handler);
        });
    },

    close: function () {
        this._getInstance().hide();
    },

    showError: function (msg) {
        var body = document.getElementById('globalModalBody');
        var existing = body.querySelector('.pp-modal-error');
        if (existing) existing.remove();
        var div = document.createElement('div');
        div.className = 'pp-alert pp-alert-danger pp-modal-error';
        div.textContent = msg;
        body.prepend(div);
    },

    createItem: function (projectKey, defaults) {
        defaults = defaults || {};
        api.get('/api/projects/' + projectKey + '/form-options').then(function (data) {
            var defEpic = defaults.epic_id || null;
            var defSprint = defaults.sprint_id || null;
            var defAssignee = defaults.assignee_id || null;

            // Apply default assignee preference if no explicit default
            if (!defAssignee && data.default_assignee === 'me' && data.current_user_id) {
                defAssignee = data.current_user_id;
            }

            var html = '<div class="pp-form-group">' +
                '<label class="pp-form-label">Title</label>' +
                '<input type="text" class="pp-input" id="modalItemTitle" required>' +
                '</div>' +
                '<div class="row g-3">' +
                '<div class="col-md-4"><div class="pp-form-group">' +
                '<label class="pp-form-label">Type</label>' +
                '<select class="pp-input pp-select" id="modalItemType">' +
                data.types.map(function (t) {
                    var isSelected = defaults.parent_id
                        ? (t.name === 'Task')
                        : t.is_default;
                    return '<option value="' + ppModal._escAttr(t.id) + '"' + (isSelected ? ' selected' : '') + '>' + ppModal._escHtml(t.name) + '</option>';
                }).join('') +
                '</select></div></div>' +
                '<div class="col-md-4"><div class="pp-form-group">' +
                '<label class="pp-form-label">Status</label>' +
                '<select class="pp-input pp-select" id="modalItemStatus">' +
                data.statuses.map(function (s) {
                    var sel = defaults.status_id == s.id || (!defaults.status_id && s.is_default);
                    return '<option value="' + ppModal._escAttr(s.id) + '"' + (sel ? ' selected' : '') + '>' + ppModal._escHtml(s.name) + '</option>';
                }).join('') +
                '</select></div></div>' +
                '<div class="col-md-4"><div class="pp-form-group">' +
                '<label class="pp-form-label">Priority</label>' +
                '<select class="pp-input pp-select" id="modalItemPriority">' +
                ['none','low','medium','high','critical'].map(function (p) {
                    return '<option value="' + p + '"' + (p === 'medium' ? ' selected' : '') + '>' + p.charAt(0).toUpperCase() + p.slice(1) + '</option>';
                }).join('') +
                '</select></div></div>' +
                '</div>' +
                '<div class="row g-3">' +
                '<div class="col-md-4"><div class="pp-form-group">' +
                '<label class="pp-form-label">Epic</label>' +
                '<select class="pp-input pp-select" id="modalItemEpic">' +
                '<option value="">None</option>' +
                data.epics.map(function (e) {
                    var sel = defEpic == e.id;
                    return '<option value="' + ppModal._escAttr(e.id) + '"' + (sel ? ' selected' : '') + '>' + ppModal._escHtml(e.name) + '</option>';
                }).join('') +
                '</select></div></div>' +
                '<div class="col-md-4"><div class="pp-form-group">' +
                '<label class="pp-form-label">Sprint</label>' +
                '<select class="pp-input pp-select" id="modalItemSprint">' +
                '<option value="">None</option>' +
                data.sprints.map(function (s) {
                    var sel = defSprint == s.id;
                    return '<option value="' + ppModal._escAttr(s.id) + '"' + (sel ? ' selected' : '') + '>' + ppModal._escHtml(s.name) + (s.is_active ? ' (Active)' : '') + '</option>';
                }).join('') +
                '</select></div></div>' +
                '<div class="col-md-4"><div class="pp-form-group">' +
                '<label class="pp-form-label">Assignee</label>' +
                '<select class="pp-input pp-select" id="modalItemAssignee">' +
                '<option value="">Unassigned</option>' +
                data.members.map(function (m) {
                    var sel = defAssignee == m.id;
                    return '<option value="' + ppModal._escAttr(m.id) + '"' + (sel ? ' selected' : '') + '>' + ppModal._escHtml(m.name) + '</option>';
                }).join('') +
                '</select></div></div>' +
                '</div>' +
                '<div class="pp-form-group">' +
                '<label class="pp-form-label">Description</label>' +
                '<textarea class="pp-input" id="modalItemDesc" rows="3"></textarea>' +
                '</div>';

            if (defaults.parent_id) {
                html += '<input type="hidden" id="modalItemParent" value="' + defaults.parent_id + '">';
            }

            ppModal.show({
                title: defaults.parent_id ? 'New Subtask' : 'New Work Item',
                body: html,
                submitLabel: 'Create',
                onSubmit: function () {
                    var payload = {
                        title: document.getElementById('modalItemTitle').value.trim(),
                        item_type_id: parseInt(document.getElementById('modalItemType').value),
                        status_id: parseInt(document.getElementById('modalItemStatus').value),
                        priority: document.getElementById('modalItemPriority').value,
                        epic_id: parseInt(document.getElementById('modalItemEpic').value) || null,
                        sprint_id: parseInt(document.getElementById('modalItemSprint').value) || null,
                        assignee_id: parseInt(document.getElementById('modalItemAssignee').value) || null,
                        description: document.getElementById('modalItemDesc').value.trim()
                    };
                    var parentEl = document.getElementById('modalItemParent');
                    if (parentEl) payload.parent_id = parseInt(parentEl.value);
                    if (!payload.title) {
                        ppModal.showError('Title is required');
                        return Promise.reject(new Error('Title is required'));
                    }
                    return api.post('/api/projects/' + projectKey + '/items', payload);
                },
                onSuccess: function () { location.reload(); }
            });
        });
    },

    pickProjectThenCreate: function (projects) {
        var html = '<div class="pp-form-group">' +
            '<label class="pp-form-label">Select a project</label>' +
            '<div class="list-group">';
        projects.forEach(function (p) {
            html += '<button type="button" class="list-group-item list-group-item-action d-flex align-items-center gap-2 pp-project-pick-btn" data-key="' + ppModal._escAttr(p.key) + '">' +
                '<span class="pp-badge-key">' + ppModal._escHtml(p.key) + '</span> ' +
                ppModal._escHtml(p.name) + '</button>';
        });
        html += '</div></div>';

        ppModal.show({
            title: 'New Work Item',
            body: html,
            submitLabel: 'Cancel',
            onSubmit: function () {
                ppModal.close();
                return Promise.resolve();
            }
        });

        // Clicking a project immediately opens the create modal for that project
        document.querySelectorAll('.pp-project-pick-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                ppModal.close();
                setTimeout(function () {
                    ppModal.createItem(btn.getAttribute('data-key'));
                }, 300);
            });
        });
    },

    createEpic: function (projectKey) {
        var html = '<div class="pp-form-group">' +
            '<label class="pp-form-label">Name</label>' +
            '<input type="text" class="pp-input" id="modalEpicName" required>' +
            '</div>' +
            '<div class="pp-form-group">' +
            '<label class="pp-form-label">Description</label>' +
            '<textarea class="pp-input" id="modalEpicDesc" rows="2"></textarea>' +
            '</div>' +
            '<div class="pp-form-group">' +
            '<label class="pp-form-label">Color</label>' +
            '<input type="color" class="form-control form-control-color" id="modalEpicColor" value="#8b5cf6">' +
            '</div>';

        ppModal.show({
            title: 'New Epic',
            body: html,
            submitLabel: 'Create',
            onSubmit: function () {
                var name = document.getElementById('modalEpicName').value.trim();
                if (!name) {
                    ppModal.showError('Name is required');
                    return Promise.reject(new Error('Name is required'));
                }
                return api.post('/api/projects/' + projectKey + '/epics', {
                    name: name,
                    description: document.getElementById('modalEpicDesc').value.trim(),
                    color: document.getElementById('modalEpicColor').value
                });
            },
            onSuccess: function () { location.reload(); }
        });
    },

    createSprint: function (projects, selectedProjectIds) {
        selectedProjectIds = selectedProjectIds || [];
        var html = '<div class="pp-form-group">' +
            '<label class="pp-form-label">Name</label>' +
            '<input type="text" class="pp-input" id="modalSprintName" required>' +
            '</div>' +
            '<div class="pp-form-group">' +
            '<label class="pp-form-label">Goal</label>' +
            '<textarea class="pp-input" id="modalSprintGoal" rows="2"></textarea>' +
            '</div>' +
            '<div class="row g-3">' +
            '<div class="col-md-6"><div class="pp-form-group">' +
            '<label class="pp-form-label">Start Date</label>' +
            '<input type="date" class="pp-input" id="modalSprintStart">' +
            '</div></div>' +
            '<div class="col-md-6"><div class="pp-form-group">' +
            '<label class="pp-form-label">End Date</label>' +
            '<input type="date" class="pp-input" id="modalSprintEnd">' +
            '</div></div></div>' +
            '<div class="pp-form-group">' +
            '<label class="pp-form-label">Projects</label>';

        projects.forEach(function (p) {
            var checked = selectedProjectIds.indexOf(p.id) >= 0 || (projects.length === 1) ? ' checked' : '';
            html += '<div class="form-check">' +
                '<input class="form-check-input" type="checkbox" name="sprint_projects" value="' + ppModal._escAttr(p.id) + '" id="spProj' + ppModal._escAttr(p.id) + '"' + checked + '>' +
                '<label class="form-check-label" for="spProj' + ppModal._escAttr(p.id) + '">' +
                '<span class="pp-badge-key me-1">' + ppModal._escHtml(p.key) + '</span>' + ppModal._escHtml(p.name) +
                '</label></div>';
        });
        html += '</div>';

        ppModal.show({
            title: 'New Sprint',
            body: html,
            submitLabel: 'Create',
            onSubmit: function () {
                var name = document.getElementById('modalSprintName').value.trim();
                if (!name) {
                    ppModal.showError('Name is required');
                    return Promise.reject(new Error('Name is required'));
                }
                var projectIds = [];
                document.querySelectorAll('input[name="sprint_projects"]:checked').forEach(function (cb) {
                    projectIds.push(parseInt(cb.value));
                });
                if (projectIds.length === 0) {
                    ppModal.showError('Select at least one project');
                    return Promise.reject(new Error('Select at least one project'));
                }
                return api.post('/api/sprints', {
                    name: name,
                    goal: document.getElementById('modalSprintGoal').value.trim(),
                    start_date: document.getElementById('modalSprintStart').value || null,
                    end_date: document.getElementById('modalSprintEnd').value || null,
                    project_ids: projectIds
                });
            },
            onSuccess: function () { location.reload(); }
        });
    }
};
