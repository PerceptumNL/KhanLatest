// Force the javascript less compiler to operate in development mode. This is
// useful because in production mode it caches imported less files in
// localStorage.
// This file is not included when javascript is packaged for production.
less = {}; less.env = 'development';
