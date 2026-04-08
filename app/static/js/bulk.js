/**
 * Bulk operations: select items and apply changes.
 * Supports cross-project selection with intersection-based options.
 */
var ppBulk = (function () {
    'use strict';

    var selected = new Set();       // item IDs
    var bulkMode = false;

    // Map projectKey -> form-options data (cached)
    var projectOptionsCache = {};
    // Set of project keys currently in the selection
    var activeProjectKeys = new Set();

    function getItemProjectKey(itemId) {
        // kanban cards have data-project-key on .kanban-card
        var el = document.querySelector('[data-item-id="' + itemId + '"]');
        if (!el) return null;
        return el.dataset.projectKey || null;
    }

    function toggleMode() {
        bulkMode = !bulkMode;
        var container = document.querySelector('.kanban-board') || document.querySelector('.pp-card');
        if (container) {
            container.classList.toggle('pp-bulk-mode', bulkMode);
        }
        document.querySelectorAll('.pp-bulk-check').forEach(function (cb) {
            cb.style.display = bulkMode ? '' : 'none';
            cb.checked = false;
        });
        selected.clear();
        activeProjectKeys.clear();
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
        rebuildActiveProjects();
        updateBar();
    }

    function rebuildActiveProjects() {
        activeProjectKeys.clear();
        selected.forEach(function (id) {
            var key = getItemProjectKey(id);
            if (key) activeProjectKeys.add(key);
        });
    }

    function updateBar() {
        var bar = document.getElementById('bulkBar');
        if (!bar) return;
        var count = selected.size;
        bar.style.display = count > 0 ? '' : 'none';
        var countEl = document.getElementById('bulkCount');
        if (countEl) countEl.textContent = count + ' selected';

        if (count > 0) {
            ensureOptionsLoaded().then(function () {
                rebuildDropdowns();
            });
        }
    }

    function ensureOptionsLoaded() {
        var promises = [];
        activeProjectKeys.forEach(function (key) {
            if (!projectOptionsCache[key]) {
                var p = api.get('/api/projects/' + key + '/form-options').then(function (data) {
                    projectOptionsCache[key] = data;
                });
                promises.push(p);
            }
        });
        return Promise.all(promises);
    }

    /**
     * Compute intersection of options across all active projects.
     * Statuses: intersect by name (return {name, color} objects present in ALL projects)
     * Assignees: intersect by user id (return {id, name} present in ALL projects)
     * Sprints: intersect by sprint id (return {id, name} present in ALL projects)
     */
    function computeIntersection() {
        var keys = Array.from(activeProjectKeys);
        if (keys.length === 0) return { statuses: [], assignees: [], sprints: [] };

        var first = projectOptionsCache[keys[0]];
        if (!first) return { statuses: [], assignees: [], sprints: [] };

        // Statuses by name
        var statusNames = {};
        first.statuses.forEach(function (s) {
            statusNames[s.name] = { name: s.name, color: s.color };
        });
        for (var i = 1; i < keys.length; i++) {
            var opts = projectOptionsCache[keys[i]];
            if (!opts) return { statuses: [], assignees: [], sprints: [] };
            var thisNames = {};
            opts.statuses.forEach(function (s) { thisNames[s.name] = true; });
            Object.keys(statusNames).forEach(function (name) {
                if (!thisNames[name]) delete statusNames[name];
            });
        }

        // Assignees by id
        var assigneeMap = {};
        first.members.forEach(function (m) {
            assigneeMap[m.id] = { id: m.id, name: m.name };
        });
        for (var i = 1; i < keys.length; i++) {
            var opts = projectOptionsCache[keys[i]];
            var thisIds = {};
            opts.members.forEach(function (m) { thisIds[m.id] = true; });
            Object.keys(assigneeMap).forEach(function (id) {
                if (!thisIds[id]) delete assigneeMap[id];
            });
        }

        // Sprints by id
        var sprintMap = {};
        first.sprints.forEach(function (s) {
            sprintMap[s.id] = { id: s.id, name: s.name };
        });
        for (var i = 1; i < keys.length; i++) {
            var opts = projectOptionsCache[keys[i]];
            var thisIds = {};
            opts.sprints.forEach(function (s) { thisIds[s.id] = true; });
            Object.keys(sprintMap).forEach(function (id) {
                if (!thisIds[id]) delete sprintMap[id];
            });
        }

        return {
            statuses: Object.values(statusNames),
            assignees: Object.values(assigneeMap),
            sprints: Object.values(sprintMap),
        };
    }

    function rebuildDropdowns() {
        var intersection = computeIntersection();
        var isCrossProject = activeProjectKeys.size > 1;

        // Status dropdown
        var statusSel = document.getElementById('bulkStatus');
        if (statusSel) {
            var currentVal = statusSel.value;
            statusSel.innerHTML = '<option value="">Change Status...</option>';
            if (intersection.statuses.length === 0 && isCrossProject) {
                statusSel.innerHTML = '<option value="">No common statuses</option>';
                statusSel.disabled = true;
            } else {
                statusSel.disabled = false;
                intersection.statuses.forEach(function (s) {
                    var opt = document.createElement('option');
                    // For cross-project, use name; for single project, use id
                    if (isCrossProject) {
                        opt.value = 'name:' + s.name;
                    } else {
                        // Single project: find the actual id
                        var key = Array.from(activeProjectKeys)[0];
                        var full = projectOptionsCache[key].statuses.find(function (st) { return st.name === s.name; });
                        opt.value = full ? full.id : '';
                    }
                    opt.textContent = s.name;
                    statusSel.appendChild(opt);
                });
            }
            // Restore selection if still valid
            if (currentVal && statusSel.querySelector('option[value="' + currentVal + '"]')) {
                statusSel.value = currentVal;
            }
        }

        // Sprint dropdown
        var sprintSel = document.getElementById('bulkSprint');
        if (sprintSel) {
            var currentVal = sprintSel.value;
            sprintSel.innerHTML = '<option value="">Change Sprint...</option>';
            if (intersection.sprints.length === 0 && isCrossProject) {
                sprintSel.innerHTML = '<option value="">No common sprints</option>';
                sprintSel.disabled = true;
            } else {
                sprintSel.disabled = false;
                var noneOpt = document.createElement('option');
                noneOpt.value = 'none';
                noneOpt.textContent = 'No Sprint';
                sprintSel.appendChild(noneOpt);
                intersection.sprints.forEach(function (s) {
                    var opt = document.createElement('option');
                    opt.value = s.id;
                    opt.textContent = s.name;
                    sprintSel.appendChild(opt);
                });
            }
            if (currentVal && sprintSel.querySelector('option[value="' + currentVal + '"]')) {
                sprintSel.value = currentVal;
            }
        }

        // Assignee dropdown
        var assigneeSel = document.getElementById('bulkAssignee');
        if (assigneeSel) {
            var currentVal = assigneeSel.value;
            assigneeSel.innerHTML = '<option value="">Change Assignee...</option>';
            if (intersection.assignees.length === 0 && isCrossProject) {
                assigneeSel.innerHTML = '<option value="">No common assignees</option>';
                assigneeSel.disabled = true;
            } else {
                assigneeSel.disabled = false;
                var unOpt = document.createElement('option');
                unOpt.value = 'none';
                unOpt.textContent = 'Unassigned';
                assigneeSel.appendChild(unOpt);
                intersection.assignees.forEach(function (m) {
                    var opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    assigneeSel.appendChild(opt);
                });
            }
            if (currentVal && assigneeSel.querySelector('option[value="' + currentVal + '"]')) {
                assigneeSel.value = currentVal;
            }
        }
    }

    function apply() {
        if (selected.size === 0) return;

        var changes = {};
        var statusVal = document.getElementById('bulkStatus').value;
        if (statusVal) {
            if (statusVal.indexOf('name:') === 0) {
                // Cross-project: send status name, backend resolves per item
                changes.status_name = statusVal.substring(5);
            } else {
                changes.status_id = parseInt(statusVal);
            }
        }
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
        activeProjectKeys.clear();
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
