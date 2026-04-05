document.addEventListener('DOMContentLoaded', function () {
    // ---- Theme Toggle ----
    var themeToggle = document.getElementById('themeToggle');
    var html = document.documentElement;
    var stored = localStorage.getItem('theme');
    if (stored) html.setAttribute('data-bs-theme', stored);
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
            sidebar.style.transform = 'translateX(-100%)';
            content.style.marginLeft = '0';
        } else {
            sidebar.style.transform = '';
            content.style.marginLeft = '';
        }
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
            if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); }
            if (ev.key === 'Escape') { input.value = current; input.blur(); }
        });
        input.addEventListener('click', function (ev) { ev.stopPropagation(); });
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
