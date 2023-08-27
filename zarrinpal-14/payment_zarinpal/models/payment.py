import logging
import requests
from odoo import api, fields, models, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment_zarinpal.controllers.main import ZarinPalController
import math

_logger = logging.getLogger(__name__)


def _get_zarinpal_urls():
    """ ZarinPal URLS """
    return {
        'zarinpal_form_url': 'https://www.zarinpal.com/pg/StartPay/',
        'zarinpal_rest_url_get_token': 'https://api.zarinpal.com/pg/v4/payment/request.json',
        'zarinpal_rest_url_verify': 'https://api.zarinpal.com/pg/v4/payment/verify.json',
    }


class AcquirerZarinPal(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('zarinpal', 'ZarinPal')], ondelete={'zarinpal': 'set default'})
    zarinpal_merchant_id = fields.Char('Merchant ID', required_if_provider='zarinpal', groups='base.group_user')

    fees_dom_limit = fields.Float(string='Upper limit for domestic fees')

    def _get_feature_support(self):
        res = super(AcquirerZarinPal, self)._get_feature_support()
        res['fees'].append('zarinpal')
        res['authorize'].append('zarinpal')
        return res

    def zarinpal_compute_fees(self, amount, currency_id, country_id):
        """ Compute zarinpal fees.

            :param float amount: the amount to pay
            :param integer country_id: an ID of a res.country, or None. This is
                                       the customer's country, to be compared to
                                       the acquirer company country.
            :return float fees: computed fees
        """
        if not self.fees_active:
            return 0.0
        percentage = self.fees_dom_var
        upper_limit = self.fees_dom_limit
        calculated_fees = math.floor(percentage * amount / 100)
        return min(calculated_fees, upper_limit)

    def zarinpal_form_generate_values(self, values):
        self.ensure_one()
        transaction = self.env['payment.transaction'].search([('reference', '=', values['reference'])])
        zarinpal_tx_values = dict(values)
        # TODO: I really do not know how is this working! this implementation is based on a guess
        new_context = dict(self.env.context)
        new_context.update(
            {'tx_url': transaction.acquirer_id.zarinpal_get_form_action_url() + transaction.acquirer_reference}
        )
        self.sudo().env.context = new_context
        return zarinpal_tx_values

    @staticmethod
    def zarinpal_get_form_action_url():
        return _get_zarinpal_urls()['zarinpal_form_url']

    @staticmethod
    def zarinpal_get_rest_url_get_token():
        return _get_zarinpal_urls()['zarinpal_rest_url_get_token']

    @staticmethod
    def zarinpal_get_rest_url_verify():
        return _get_zarinpal_urls()['zarinpal_rest_url_verify']


class TxZarinPal(models.Model):
    _inherit = 'payment.transaction'

    zarinpal_tx_ref_id = fields.Char('ZarinPal TransactionReferenceID')
    zarinpal_masked_card_number = fields.Char('ZarinPal Masked Card Number')
    zarinpal_hashed_card_number = fields.Char('ZarinPal Hashed Card Number')
    zarinpal_fee_type = fields.Char('ZarinPal Fee Type')
    zarinpal_fee = fields.Integer('ZarinPal Fee')

    def _get_banking_required_document_name(self, data):
        if data.get('invoice_ids'):
            return self.env['account.move'].browse(data['invoice_ids'][0][2][0]).name
        elif data.get('sale_order_ids'):
            return self.env['sale.order'].browse(data['sale_order_ids'][0][2][0]).name
        else:
            raise ValidationError(_("Can't process payment without invoice and/or sale order!"))

    def zarinpal_create(self, data):
        acquirer = self.env['payment.acquirer'].browse(data['acquirer_id'])
        payload = {
            'merchant_id': acquirer.zarinpal_merchant_id,
            'amount': int(data['amount']),
            'description': self._get_banking_required_document_name(data),
            'callback_url': acquirer.get_base_url() + ZarinPalController.redirect_url,
        }
        if data['partner_phone'] or data['partner_email']:
            metadata_dict = {}
            if data['partner_phone']:
                metadata_dict['mobile'] = data['partner_phone']
            if data['partner_email']:
                metadata_dict['email'] = data['partner_email']
            payload['metadata'] = metadata_dict
        url = acquirer.zarinpal_get_rest_url_get_token()
        try:
            custom_header = {"accept": "application/json", "content-type": "application/json'"}
            req = requests.post(url, json=payload, headers=custom_header, timeout=15)
            req.raise_for_status()
            response = req.json()
            if response['data'] and response['data']['code'] == 100:
                data['acquirer_reference'] = response['data']['authority']
                data['state'] = 'pending'
            elif response['errors'] and response['errors']['message']:
                if response['errors']['validations']:
                    raise ValidationError(f"{response['errors']['message']}, {response['errors']['validations']}")
                else:
                    raise ValidationError(response['errors']['message'])
            else:
                raise ValidationError(_('Error occurred in getting token from ZarinPal!'))
        except Exception as e:
            raise ValidationError(e.args[0])
        return data

    @api.model
    def _zarinpal_form_get_tx_from_data(self, data):
        authority, status = data.get('Authority'), data.get('Status')
        if not authority or not status:
            error_msg = 'ZarinPal: received data with missing authority (%s) or status (%s)' % (authority, status)
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        txs = self.env['payment.transaction'].search([('acquirer_reference', '=', authority)])
        if not txs or len(txs) > 1:
            error_msg = 'ZarinPal: received data for authority %s' % (authority)
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    def _zarinpal_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        _logger.info('Received a notification from ZarinPal with authority version %s', data.get('Authority'))
        if data.get('Status') != 'OK':
            invalid_parameters.append(('Status', data.get('Status'), 'OK'))
        return invalid_parameters

    def _zarinpal_form_validate(self, data):
        url = self.acquirer_id.zarinpal_get_rest_url_verify()
        payload = {
            'merchant_id': self.acquirer_id.zarinpal_merchant_id,
            'amount': int(self.amount),
            'authority': self.acquirer_reference,
        }
        try:
            custom_header = {"accept": "application/json", "content-type": "application/json'"}
            req = requests.post(url, json=payload, headers=custom_header, timeout=15)
            req.raise_for_status()
            response = req.json()
            if response['data'] and response['data']['code'] in [100, 101]:
                if response['data'].get('card_pan', None):
                    self.zarinpal_masked_card_number = response['data']['card_pan']
                if response['data'].get('card_hash', None):
                    self.zarinpal_hashed_card_number = response['data']['card_hash']
                if response['data'].get('ref_id', None):
                    self.zarinpal_tx_ref_id = response['data']['ref_id']
                if response['data'].get('fee_type', None):
                    self.zarinpal_fee_type = response['data']['fee_type']
                if response['data'].get('fee', None):
                    self.zarinpal_fee = response['data']['fee']
                self._set_transaction_done()
            elif response['errors'] and response['errors']['message']:
                if response['errors']['validations']:
                    raise ValidationError(f"{response['errors']['message']}, {response['errors']['validations']}")
                else:
                    raise ValidationError(response['errors']['message'])
            else:
                raise ValidationError(_('Error occurred in verifying transaction from ZarinPal!'))
        except Exception as e:
            self._set_transaction_error(e.args[0])
            return False
        return True
