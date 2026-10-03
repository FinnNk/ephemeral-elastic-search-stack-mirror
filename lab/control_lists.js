/* Shared list navigation for the control page and its report queries. */
(function (root) {
  'use strict';
  function searchText(row, fields) {
    return fields.map(field => String(row[field] ?? '')).join(' ').toLocaleLowerCase('en-GB');
  }
  function select(rows, {search = '', fields = [], filters = {}, order = 'newest', page = 1, size = 12} = {}) {
    const terms = search.trim().toLocaleLowerCase('en-GB').split(/\s+/).filter(Boolean);
    const matches = rows.filter(row => Object.entries(filters).every(([key, value]) =>
      !value || (value === 'active' ? row[key] !== 'deleted' : row[key] === value)) &&
      terms.every(term => searchText(row, fields).includes(term)));
    if (order === 'name') matches.sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    else if (order === 'newest' || order === 'oldest') matches.sort((a, b) => {
      const result = String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')) || b.id.localeCompare(a.id);
      return order === 'oldest' ? -result : result;
    });
    size = Math.max(1, Math.min(100, Number(size) || 12));
    const pages = Math.max(1, Math.ceil(matches.length / size));
    page = Math.max(1, Math.min(pages, Number(page) || 1));
    const start = (page - 1) * size;
    return {rows: matches.slice(start, start + size), total: matches.length, page, pages,
            first: matches.length ? start + 1 : 0, last: Math.min(start + size, matches.length)};
  }
  root.ControlLists = {select};
  if (typeof module !== 'undefined') module.exports = {select};
})(typeof globalThis !== 'undefined' ? globalThis : this);
