"""Canonical searchable product schema for ESCI and the demo subset."""
MAPPING = {'settings': {'number_of_shards': 1, 'number_of_replicas': 0,
                        'refresh_interval': '30s'},
           'mappings': {'dynamic': 'strict', 'properties': {
               'product_id': {'type': 'keyword'}, 'sku': {'type': 'keyword'},
               'title': {'type': 'text'}, 'description': {'type': 'text'},
               'bullets': {'type': 'text'}, 'attrs': {'type': 'object', 'enabled': False},
               'category_path': {'type': 'keyword'}, 'brand': {'type': 'text'},
               'product_type': {'type': 'text'}, 'category': {'type': 'keyword'},
               'colour': {'type': 'keyword'}, 'material': {'type': 'keyword'},
               'country': {'type': 'keyword'}, 'currency': {'type': 'keyword'},
               'price_minor': {'type': 'integer'}, 'available': {'type': 'boolean'},
               'popularity': {'type': 'float'}, 'rating': {'type': 'float'},
               'review_count': {'type': 'integer'},
           }}}
