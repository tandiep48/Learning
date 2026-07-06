(function () {
    // Reads window.translations (bootstrapped server-side in site_nav.html) with English fallback via the key itself.
    function lookup(key) {
        const parts = key.split('.');
        let node = window.translations || {};
        for (const part of parts) {
            if (node && typeof node === 'object' && part in node) {
                node = node[part];
            } else {
                return key;
            }
        }
        return typeof node === 'string' ? node : key;
    }

    function t(key, vars) {
        let str = lookup(key);
        if (vars) {
            Object.keys(vars).forEach(name => {
                str = str.replace(new RegExp(`\\{${name}\\}`, 'g'), vars[name]);
            });
        }
        return str;
    }

    window.t = t;
})();
