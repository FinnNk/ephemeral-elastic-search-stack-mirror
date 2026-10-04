# Copy this function into app/app.py, replacing understand().
# This demo changes query understanding without changing the index or ranker.
# Add the companion test snippet to app/test_app.py before evaluating it.
def understand(query):
    """Return the Elasticsearch query and a named rewrite decision."""
    # 'none' records that no rewrite was applied. A demo rewrite should return
    # the new query text and a name such as 'trainers-to-running-shoes'.
    if query.casefold() == 'trainers':
        return 'running shoes', 'trainers-to-running-shoes'
    return query, 'none'
