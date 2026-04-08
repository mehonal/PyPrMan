document.addEventListener('DOMContentLoaded', function () {
    // ---- Theme Toggle ----
    var themeToggle = document.getElementById('themeToggle');
    var html = document.documentElement;
    updateThemeIcon();

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            var next = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-bs-theme', next);
            localStorage.setItem('theme', next);
            updateThemeIcon();
        });
    }

    function updateThemeIcon() {
        if (!themeToggle) return;
        var icon = themeToggle.querySelector('i');
        icon.className = html.getAttribute('data-bs-theme') === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    }

    // ---- Sidebar Toggle (Desktop) ----
    var sidebar = document.getElementById('sidebar');
    var content = document.getElementById('content');
    var sidebarToggle = document.getElementById('sidebarToggle');

    if (sidebarToggle && sidebar) {
        var collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (collapsed) setSidebarCollapsed(true);

        sidebarToggle.addEventListener('click', function () {
            collapsed = !collapsed;
            setSidebarCollapsed(collapsed);
            localStorage.setItem('sidebarCollapsed', collapsed);
        });
    }

    function setSidebarCollapsed(state) {
        if (state) {
            document.body.classList.add('pp-sidebar-collapsed');
        } else {
            document.body.classList.remove('pp-sidebar-collapsed');
        }
    }

    // ---- Sidebar Expand (from topbar when collapsed) ----
    var sidebarExpand = document.getElementById('sidebarExpand');
    if (sidebarExpand) {
        sidebarExpand.addEventListener('click', function () {
            collapsed = false;
            setSidebarCollapsed(false);
            localStorage.setItem('sidebarCollapsed', false);
        });
    }

    // ---- Sidebar Toggle (Mobile) ----
    var mobileToggle = document.getElementById('mobileToggle');
    var backdrop = document.getElementById('sidebarBackdrop');

    if (mobileToggle && sidebar && backdrop) {
        mobileToggle.addEventListener('click', function () {
            sidebar.classList.add('open');
            backdrop.classList.add('open');
        });

        backdrop.addEventListener('click', closeMobileSidebar);

        function closeMobileSidebar() {
            sidebar.classList.remove('open');
            backdrop.classList.remove('open');
        }
    }

    // ---- Project Sub-nav Expand/Collapse ----
    document.querySelectorAll('.pp-project-item').forEach(function (item) {
        item.addEventListener('click', function (e) {
            var group = item.closest('.pp-project-group');
            var subnav = group ? group.querySelector('.pp-project-subnav') : null;
            if (subnav) {
                var isOpen = subnav.classList.contains('open');
                // Close all others
                document.querySelectorAll('.pp-project-subnav.open').forEach(function (el) {
                    if (el !== subnav) el.classList.remove('open');
                });
                document.querySelectorAll('.pp-project-item.active').forEach(function (el) {
                    if (el !== item) el.classList.remove('active');
                });
                subnav.classList.toggle('open', !isOpen);
                item.classList.toggle('active', !isOpen);
                // Update chevron
                var chevron = item.querySelector('.bi-chevron-right, .bi-chevron-down');
                if (chevron) {
                    chevron.className = !isOpen ? 'bi bi-chevron-down' : 'bi bi-chevron-right';
                    chevron.style.marginLeft = 'auto';
                    chevron.style.fontSize = '0.625rem';
                    chevron.style.opacity = '0.5';
                }
                e.preventDefault();
            }
        });
    });

    // ---- Story Points quick-edit ----
    document.addEventListener('click', function (e) {
        var badge = e.target.closest('[data-sp-edit]');
        if (!badge) return;
        e.preventDefault();
        e.stopPropagation();
        if (badge.querySelector('input')) return;

        var itemId = badge.dataset.itemId;
        var current = badge.dataset.sp || '';
        var originalText = badge.textContent;

        var input = document.createElement('input');
        input.type = 'number';
        input.min = '0';
        input.value = current;
        input.style.cssText = 'width:40px; padding:1px 3px; font-size:0.6875rem; font-family:var(--pp-font-mono); text-align:center; border:1px solid var(--pp-primary); border-radius:3px; background:var(--pp-surface); color:var(--pp-text); outline:none;';

        badge.textContent = '';
        badge.appendChild(input);
        input.focus();
        input.select();

        function save() {
            var raw = input.value.trim();
            var val = raw === '' ? null : parseInt(raw);
            badge.textContent = val !== null ? val : '\u2014';
            badge.dataset.sp = raw;

            if (raw !== current) {
                api.patch('/api/items/' + itemId, { story_points: val }).catch(function () {
                    badge.textContent = originalText;
                    badge.dataset.sp = current;
                });
            }
        }

        input.addEventListener('blur', save);
        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') { ev.preventDefault(); ev.stopPropagation(); input.blur(); }
            if (ev.key === 'Escape') { ev.stopPropagation(); input.value = current; input.blur(); }
        });
        input.addEventListener('click', function (ev) { ev.preventDefault(); ev.stopPropagation(); });
    });

    // ---- Global Search ----
    var searchInput = document.getElementById('globalSearch');
    var searchResults = document.getElementById('searchResults');
    var searchWrapper = document.getElementById('searchWrapper');
    var searchToggle = document.getElementById('searchToggle');
    var searchTimer = null;

    if (searchToggle && searchWrapper) {
        searchToggle.addEventListener('click', function () {
            searchWrapper.classList.add('open');
            setTimeout(function () { searchInput.focus(); }, 50);
        });
    }

    function closeSearch() {
        searchResults.style.display = 'none';
        if (searchWrapper) searchWrapper.classList.remove('open');
    }

    if (searchInput && searchResults) {
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimer);
            var q = searchInput.value.trim();
            if (q.length < 2) {
                searchResults.style.display = 'none';
                return;
            }
            searchTimer = setTimeout(function () {
                api.get('/api/search?q=' + encodeURIComponent(q)).then(function (data) {
                    if (!data.results.length) {
                        searchResults.innerHTML = '<div class="pp-search-empty">No results found</div>';
                    } else {
                        searchResults.innerHTML = data.results.map(function (r) {
                            return '<a href="/projects/' + r.project_key + '/items/' + r.item_key + '" class="pp-search-result">' +
                                '<i class="' + r.type_icon + '" style="color:' + r.type_color + '; font-size:0.875rem;"></i>' +
                                '<span class="result-key">' + r.item_key + '</span>' +
                                '<span class="result-title">' + r.title.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span>' +
                                '<span class="pp-status-dot" style="background:' + r.status_color + '" title="' + r.status + '"></span>' +
                                '</a>';
                        }).join('');
                    }
                    searchResults.style.display = 'block';
                });
            }, 250);
        });

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeSearch();
                searchInput.blur();
            }
        });

        document.addEventListener('click', function (e) {
            if (!e.target.closest('.pp-search-wrapper')) {
                closeSearch();
            }
        });
    }

    // ---- Quick Priority Edit (board + backlog) ----
    var priorityOptions = [
        {value: 'none', label: 'None', icon: 'bi bi-dash', cls: 'pp-priority-none'},
        {value: 'low', label: 'Low', icon: 'bi bi-chevron-down', cls: 'pp-priority-low'},
        {value: 'medium', label: 'Medium', icon: 'bi bi-chevron-up', cls: 'pp-priority-medium'},
        {value: 'high', label: 'High', icon: 'bi bi-chevron-double-up', cls: 'pp-priority-high'},
        {value: 'critical', label: 'Critical', icon: 'bi bi-exclamation-triangle-fill', cls: 'pp-priority-critical'},
    ];

    function positionDropdown(dd, badge) {
        var rect = badge.getBoundingClientRect();
        dd.style.position = 'fixed';
        dd.style.zIndex = '1100';
        // Try below the badge, aligned right
        var top = rect.bottom + 2;
        var left = rect.right - 140;
        if (left < 8) left = 8;
        // If it would go off bottom, show above
        if (top + 220 > window.innerHeight) top = rect.top - 220;
        if (top < 8) top = 8;
        dd.style.top = top + 'px';
        dd.style.left = left + 'px';
    }

    document.addEventListener('click', function (e) {
        var badge = e.target.closest('[data-quick-priority]');
        if (!badge) return;
        e.preventDefault();
        e.stopPropagation();
        if (document.querySelector('.pp-quick-dropdown')) return;

        var itemId = badge.dataset.itemId;
        var current = badge.dataset.current;

        var dd = document.createElement('div');
        dd.className = 'pp-quick-dropdown';

        priorityOptions.forEach(function (opt) {
            var row = document.createElement('div');
            row.className = 'pp-quick-option';
            if (opt.value === current) row.classList.add('selected');
            row.innerHTML = '<span class="pp-priority-badge ' + opt.cls + '"><i class="' + opt.icon + '"></i></span> ' + opt.label;
            row.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                api.patch('/api/items/' + itemId, {priority: opt.value}).then(function (res) {
                    if (res.ok) {
                        badge.className = badge.className.replace(/pp-priority-\w+/g, '') + ' pp-priority-' + opt.value;
                        badge.title = opt.label;
                        badge.dataset.current = opt.value;
                        var icon = badge.querySelector('i');
                        if (icon) icon.className = res.item.priority_icon || opt.icon;
                    }
                });
                closeQuickDropdown();
            });
            dd.appendChild(row);
        });

        document.body.appendChild(dd);
        positionDropdown(dd, badge);

        var backdrop = document.createElement('div');
        backdrop.className = 'pp-quick-backdrop';
        backdrop.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            closeQuickDropdown();
        });
        document.body.appendChild(backdrop);

        function closeQuickDropdown() {
            if (dd.parentNode) dd.parentNode.removeChild(dd);
            if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
        }
    });

    // ---- Quick Assignee Edit (board + backlog) ----
    var membersCache = {};

    function getMembers(projectKey, callback) {
        if (membersCache[projectKey]) {
            callback(membersCache[projectKey]);
            return;
        }
        api.get('/api/projects/' + projectKey + '/form-options').then(function (data) {
            membersCache[projectKey] = data.members;
            callback(data.members);
        });
    }

    document.addEventListener('click', function (e) {
        var badge = e.target.closest('[data-quick-assignee]');
        if (!badge) return;
        e.preventDefault();
        e.stopPropagation();
        if (document.querySelector('.pp-quick-dropdown')) return;

        var itemId = badge.dataset.itemId;
        var projectKey = badge.dataset.projectKey;
        var current = badge.dataset.current;

        getMembers(projectKey, function (members) {
            var dd = document.createElement('div');
            dd.className = 'pp-quick-dropdown';

            var unassign = document.createElement('div');
            unassign.className = 'pp-quick-option';
            if (!current) unassign.classList.add('selected');
            unassign.textContent = 'Unassigned';
            unassign.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                api.patch('/api/items/' + itemId, {assignee_id: null}).then(function (res) {
                    if (res.ok) {
                        badge.childNodes[0].textContent = '\u2014';
                        badge.dataset.current = '';
                    }
                });
                closeQuickDropdown();
            });
            dd.appendChild(unassign);

            members.forEach(function (m) {
                var row = document.createElement('div');
                row.className = 'pp-quick-option';
                if (String(m.id) === String(current)) row.classList.add('selected');
                row.textContent = m.name;
                row.addEventListener('click', function (ev) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    api.patch('/api/items/' + itemId, {assignee_id: m.id}).then(function (res) {
                        if (res.ok) {
                            badge.childNodes[0].textContent = m.name.substring(0, 8);
                            badge.dataset.current = m.id;
                        }
                    });
                    closeQuickDropdown();
                });
                dd.appendChild(row);
            });

            document.body.appendChild(dd);
            positionDropdown(dd, badge);

            var backdrop = document.createElement('div');
            backdrop.className = 'pp-quick-backdrop';
            backdrop.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                closeQuickDropdown();
            });
            document.body.appendChild(backdrop);

            function closeQuickDropdown() {
                if (dd.parentNode) dd.parentNode.removeChild(dd);
                if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
            }
        });
    });

    // ---- Auto-dismiss alerts after 5s ----
    document.querySelectorAll('.pp-alert').forEach(function (alert) {
        setTimeout(function () {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 300ms';
            setTimeout(function () { alert.remove(); }, 300);
        }, 5000);
    });
});
