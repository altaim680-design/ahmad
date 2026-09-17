# -*- coding: utf-8 -*-
from web_sporthub_customer_email_v11 import app, premium_storefront_v11

# Keep the public root as the customer storefront; administration remains under
# /sporthub/admin/login and customer identity is handled by email OTP.
app.view_functions['sporthub_home'] = premium_storefront_v11
if 'sporthub_customer_shop' in app.view_functions:
    app.view_functions['sporthub_customer_shop'] = premium_storefront_v11

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT','5000')))
