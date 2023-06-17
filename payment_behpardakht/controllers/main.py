# -*- coding: utf-8 -*-

import logging
import pprint

import werkzeug

from odoo import http, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class BehpardakhtController(http.Controller):
    _accept_url = '/payment/behpardakht/accept'

    @staticmethod
    def behpardakht_validate_data(**post):
        """ Behpardakht contacts using GET, at least for accept """
        _logger.info('Behpardakht: entering form_feedback with post data %s', pprint.pformat(post))  # debug
        RefId = post.get('RefId')
        tx = None
        if RefId:
            tx = request.env['payment.transaction'].sudo().search([('behpardakht_refid', '=', RefId)])

        res = request.env['payment.transaction'].sudo().form_feedback(post, 'behpardakht')
        _logger.info('Behpardakht: validated data')
        if not res and tx:
            tx._set_transaction_error(_('Validation error occured. Please contact your administrator.'))

        return res

    @http.route([_accept_url], type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def behpardakht_form_feedback(self, **post):
        """
        The session cookie created by Odoo has not the attribute SameSite. Most of browsers will force this attribute
        with the value 'Lax'. After the payment, Behpardakht will perform a POST request on this route. For all these
        reasons, the cookie won't be added to the request. As a result, if we want to save the session, the server will
        create a new session cookie. Therefore, the previous session and all related information will be lost, so it
        will lead to undesirable behaviors. This is the reason why `save_session=False` is needed.
        """
        _logger.info('Behpardakht IPN form_feedback with post data %s', pprint.pformat(post))  # debug
        try:
            self.behpardakht_validate_data(**post)
        except ValidationError:
            _logger.exception('Unable to validate the Paypal payment')

        return werkzeug.utils.redirect('/payment/process')
