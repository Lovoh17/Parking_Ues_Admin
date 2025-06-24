$(document).ready(function() {
    // Elementos del DOM
    const $body = $('body');
    const $sidebarCollapse = $('#sidebarCollapse');
    const $navLinks = $('.nav-link');
    const $cards = $('.card');
    const $networkStatus = $('#networkStatus');
    const $networkIcon = $('#networkIcon');
    const $networkText = $('#networkText');

    // 1. Gestión del Sidebar
    function initSidebar() {
        // Toggle con animación
        $sidebarCollapse.on('click', function() {
            $body.toggleClass('sidebar-collapsed');
            localStorage.setItem('sidebarCollapsed', $body.hasClass('sidebar-collapsed'));
        });

        // Cargar estado guardado
        if (localStorage.getItem('sidebarCollapsed') === 'true') {
            $body.addClass('sidebar-collapsed');
        }
    }

    // 2. Navegación activa
    function setActiveNavItem() {
        const currentUrl = window.location.pathname;
        $navLinks.removeClass('active').filter(function() {
            return $(this).attr('href') === currentUrl;
        }).addClass('active');
    }

    // 3. Animación de tarjetas
    function animateCards() {
        $cards.each(function(index) {
            $(this).css('animation-delay', `${index * 0.1}s`);
        });
    }

    // 4. Gestión del estado de red
    function updateNetworkUI(status) {
        const classes = {
            checking: ['fa-spinner', 'Verificando'],
            online: ['fa-wifi', 'Online'],
            offline: ['fa-wifi-slash', 'Offline']
        };

        $networkStatus
            .removeClass('checking online offline')
            .addClass(status);

        $networkIcon
            .removeClass('fa-spinner fa-wifi fa-wifi-slash')
            .addClass(classes[status][0]);

        $networkText.text(classes[status][1]);
    }

    async function checkNetworkStatus() {
        updateNetworkUI('checking');
        
        try {
            if (!navigator.onLine) throw new Error('Offline');
            
            // Prueba de conexión real
            await fetch('https://www.google.com/favicon.ico', {
                method: 'HEAD',
                mode: 'no-cors',
                cache: 'no-store'
            });
            
            updateNetworkUI('online');
        } catch (error) {
            updateNetworkUI('offline');
        }
    }

    function initNetworkMonitoring() {
        // Configurar tooltip
        $networkStatus.tooltip({
            title: 'Estado de conexión a internet',
            placement: 'bottom'
        });

        // Event listeners
        window.addEventListener('online', () => setTimeout(checkNetworkStatus, 500));
        window.addEventListener('offline', () => updateNetworkUI('offline'));
        $(window).on('focus', checkNetworkStatus);

        // Verificación inicial y periódica
        checkNetworkStatus();
        setInterval(checkNetworkStatus, 30000);
    }

    // Inicialización
    initSidebar();
    setActiveNavItem();
    animateCards();
    initNetworkMonitoring();
});