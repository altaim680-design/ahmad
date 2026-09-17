# -*- coding: utf-8 -*-
from web_sporthub_product_images_v10 import app, premium_storefront_v10

# web_sporthub_storefront_v3 registered the original endpoint earlier during import.
# Point that existing endpoint to the V10 renderer so uploaded product images are
# visible to customers without registering routes after the startup self-tests.
app.view_functions['sporthub_home'] = premium_storefront_v10

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT','5000')))