/**
 * Bulk operations: select items and apply changes.
 */
var ppBulk = (function () {
    'use strict';

    var selected = new Set();
    var bulkMode = false;
    var optionsLoaded = false;

    function toggleMode() {
        bulkMode = !bulkMode;
        var container = document.querySelector('.kanban-board') || document.querySelector('.pp-card');
        if (container) {
            container.classList.toggle('pp-bulk-mode', bulkMode);
        }
        // Toggle checkboxes visibility
        document.querySelectorAll('.pp-bulk-check').forEach(function (cb) {
            cb.style.display = bulkMode ? '' : 'none';
            cb.checked = false;
        });
        selected.clear();
        updateBar();

        var btn = document.getElementById('bulkToggleBtn');
        if (btn) {
            btn.classList.toggle('pp-btn-primary', bulkMode);
            btn.classList.toggle('pp-btn-secondary', !bulkMode);
        }
    }

    function toggle(itemId, checked) {
        if (checked) {
            selected.add(itemId);
        } else {
            selected.delete(itemId);
        }
        updateBar();
    }

    function updateBar() {
        var bar = document.getElementById('bulkBar');
        if (!bar) return;
        var count = selected.size;
        bar.style.display = count > 0 ? '' : 'none';
        var countEl = document.getElementById('bulkCount');
        if (countEl) countEl.textContent = count + ' selected';

        if (count > 0 && !optionsLoaded) {
            loadOptions();
        }
    }

    function loadOptions() {
        // Find a project key from the page
        var projectKey = null;
        var keyEl = document.querySelector('[data-project-key]');
        if (keyEl) projectKey = keyEl.dataset.projectKey;
        if (!projectKey) {
            // Try breadcrumb
            var crumbs = document.querySelectorAll('.breadcrumb-item a');
            for (var i = 0; i < crumbs.length; i++) {
                var href = crumbs[i].getAttribute('href');
                if (href && href.indexOf('/projects/') === 0) {
                    var parts = href.split('/');
                    projectKey = parts[2];
                    break;
                }
            }
        }
        if (!projectKey) return;

        api.get('/api/projects/' + projectKey + '/form-options').then(function (data) {
            optionsLoaded = true;
            var statusSel = document.getElementById('bulkStatus');
            if (statusSel) {
                data.statuses.forEach(function (s) {
                    var opt = document.createElement('option');
                    opt.value = s.id;
                    opt.textContent = s.name;
                    statusSel.appendChild(opt);
                });
            }
            var sprintSel = document.getElementById('bulkSprint');
            if (sprintSel) {
                var noneOpt = document.createElement('option');
                noneOpt.value = 'none';
                noneOpt.textContent = 'No Sprint';
                sprintSel.appendChild(noneOpt);
                data.sprints.forEach(function (s) {
                    var opt = document.createElement('option');
                    opt.value = s.id;
                    opt.textContent = s.name;
                    sprintSel.appendChild(opt);
                });
            }
            var assigneeSel = document.getElementById('bulkAssignee');
            if (assigneeSel) {
                var unOpt = document.createElement('option');
                unOpt.value = 'none';
                unOpt.textContent = 'Unassigned';
                assigneeSel.appendChild(unOpt);
                data.members.forEach(function (m) {
                    var opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    assigneeSel.appendChild(opt);
                });
            }
        });
    }

    function apply() {
        if (selected.size === 0) return;

        var changes = {};
        var statusVal = document.getElementById('bulkStatus').value;
        if (statusVal) changes.status_id = parseInt(statusVal);
        var sprintVal = document.getElementById('bulkSprint').value;
        if (sprintVal) changes.sprint_id = sprintVal === 'none' ? null : parseInt(sprintVal);
        var assigneeVal = document.getElementById('bulkAssignee').value;
        if (assigneeVal) changes.assignee_id = assigneeVal === 'none' ? null : parseInt(assigneeVal);
        var priorityVal = document.getElementById('bulkPriority').value;
        if (priorityVal) changes.priority = priorityVal;

        if (Object.keys(changes).length === 0) return;

        api.patch('/api/items/bulk', {
            item_ids: Array.from(selected),
            changes: changes,
        }).then(function (res) {
            if (res.ok) location.reload();
        }).catch(function (err) {
            console.error('Bulk update failed:', err);
        });
    }

    function deleteSelected() {
        if (selected.size === 0) return;
        if (!confirm('Delete ' + selected.size + ' item(s)?')) return;

        api.del('/api/items/bulk', {
            item_ids: Array.from(selected),
        }).then(function (res) {
            if (res.ok) location.reload();
        }).catch(function (err) {
            console.error('Bulk delete failed:', err);
        });
    }

    function cancel() {
        selected.clear();
        document.querySelectorAll('.pp-bulk-check').forEach(function (cb) {
            cb.checked = false;
        });
        updateBar();
    }

    // Bind apply button
    document.addEventListener('DOMContentLoaded', function () {
        var applyBtn = document.getElementById('bulkApply');
        if (applyBtn) applyBtn.addEventListener('click', apply);
    });

    return {
        toggleMode: toggleMode,
        toggle: toggle,
        cancel: cancel,
        deleteSelected: deleteSelected,
    };
})();
