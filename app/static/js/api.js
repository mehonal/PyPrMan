var api = {
    csrfToken: function () {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    },

    request: function (method, url, data) {
        var headers = { 'X-CSRFToken': this.csrfToken() };
        var opts = { method: method, headers: headers };

        if (data !== undefined) {
            headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(data);
        }

        return fetch(url, opts).then(function (res) {
            if (!res.ok) {
                return res.json().then(function (err) {
                    throw new Error(err.error || 'Request failed');
                }).catch(function () {
                    throw new Error('Request failed (' + res.status + ')');
                });
            }
            return res.json();
        });
    },

    get: function (url) { return this.request('GET', url); },
    post: function (url, data) { return this.request('POST', url, data); },
    patch: function (url, data) { return this.request('PATCH', url, data); },
    del: function (url) { return this.request('DELETE', url); }
};
