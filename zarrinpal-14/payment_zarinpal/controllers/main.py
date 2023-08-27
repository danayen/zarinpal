import logging
import werkzeug
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ZarinPalController(http.Controller):
    redirect_url = 'payment/zarinpal/redirect/'

    @http.route('/payment/zarinpal/redirect/', type='http', auth='public', csrf=False)
    def zarinpal_redirect(self, **get):
        _logger.info(f'request from: {request.httprequest.remote_addr}, with content: {get}')
        request.env['payment.transaction'].sudo().form_feedback(get, 'zarinpal')
        return werkzeug.utils.redirect("/payment/process")
