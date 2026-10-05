# Copy this function into app/app.py, replacing understand().
# Keep the existing trainers rewrite and add sneakers for this demo.
def understand(query):
    """Return the Elasticsearch query and a named rewrite decision."""
    rewrites = {
        'trainers': ('running shoes', 'trainers-to-running-shoes'),
        'sneakers': ('running shoes', 'sneakers-to-running-shoes'),
    }
    # 'none' means the original query is passed through unchanged.
    return rewrites.get(query.casefold(), (query, 'none'))
