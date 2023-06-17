# coding: utf-8

import datetime
import logging

from odoo.addons.payment_behpardakht.controllers.main import BehpardakhtController
from werkzeug import urls

from zeep import Client

from odoo import api, fields, models, _
from odoo.addons.payment.models.payment_acquirer import ValidationError

_logger = logging.getLogger(__name__)

BEHPARDAKHT_ERROR_MAP = {
    '0': _('Transaction Approved'),
    '11': _('Invalid Card Number'),
    '12': _('No Sufficient Funds'),
    '13': _('Incorrect Pin'),
    '14': _('Allowable Number Of Pin Tries Exceeded'),
    '15': _('Card Not Effective'),
    '16': _('Exceeds Withdrawal Frequency Limit'),
    '17': _('Customer Cancellation'),
    '18': _('Expired Card'),
    '19': _('Exceeds Withdrawal Amount Limit'),
    '111': _('No Such Issuer'),
    '112': _('Card Switch Internal Error'),
    '113': _('Issuer Or Switch Is Inoperative'),
    '114': _('Transaction Not Permitted To Card Holder'),
    '21': _('Invalid Merchant'),
    '23': _('Security Violation'),
    '24': _('Invalid User Or Password'),
    '25': _('Invalid Amount'),
    '31': _('Invalid Response'),
    '32': _('Format Error'),
    '33': _('No Investment Account'),
    '34': _('System Internal Error'),
    '35': _('Invalid Business Date'),
    '41': _('Duplicate Order Id'),
    '42': _('Sale Transaction Not Found'),
    '43': _('Duplicate Verify'),
    '44': _('Verify Transaction Not Found'),
    '45': _('Transaction Has Been Settled'),
    '46': _('Transaction Has Not Been Settled'),
    '47': _('Settle Transaction Not Found'),
    '48': _('Transaction Has Been Reversed'),
    '49': _('Refund Transaction Not Found'),
    '412': _('Bill Digit Incorrect'),
    '413': _('Payment Digit Incorrect'),
    '414': _('Bill Organization Not Valid'),
    '415': _('Session Timeout'),
    '416': _('Data Access Exception'),
    '417': _('Payer Id Is Invalid'),
    '418': _('Customer Not Found'),
    '419': _('Try Count Exceeded'),
    '421': _('Invalid IP'),
    '51': _('Duplicate Transmission'),
    '54': _('Original Transaction Not Found'),
    '55': _('Invalid Transaction'),
    '61': _('Error In Settle'),
}


class AcquirerBehpardakht(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('behpardakht', 'Behpardakht Mellat')], ondelete={'behpardakht': 'set default'})
    bp_terminal_id = fields.Integer(string='Terminal Id', required_if_provider='behpardakht', help='Merchant Terminal ID', groups='base.group_user')
    bp_username = fields.Char(string='Merchant Username', required_if_provider='behpardakht', groups='base.group_user')
    bp_password = fields.Char(string='Merchant Password', required_if_provider='behpardakht', groups='base.group_user')

    def _get_behpardakht_urls(self, environment):
        """ Behpardakht URLS """
        if environment == 'prod':
            return {
                'behpardakht_wsdl_url': 'https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl',
                'behpardakht_order_url': 'https://bpm.shaparak.ir/pgwchannel/startpay.mellat',
            }
        else:
            return {
                'behpardakht_wsdl_url': 'https://banktest.ir/gateway/bpm.shaparak.ir/pgwchannel/services/pgw?wsdl',
                'behpardakht_order_url': 'https://banktest.ir/gateway/pgw.bpm.bankmellat.ir/pgwchannel/startpay.mellat',
            }

    def _bp_request(self, params, method):
        try:
            params.update({
                'terminalId': self.bp_terminal_id,
                'userName': self.bp_username,
                'userPassword': self.bp_password,
            })

            WSDL_link = self.behpardakht_get_wsdl_url()
            client = Client(WSDL_link)
            # BPM PGW Method Call
            response = getattr(client.service, method)(**params)
        except Exception as e:
            # Error connecting to Mellat Bank
            _logger.exception(str(e))  # debug
            response = None
        return response

    def _bp_default_params(self, params):
        return dict(
            orderId=params.get('orderId'),
            saleOrderId=params.get('saleOrderId'),
            saleReferenceId=params.get('saleReferenceId')
        )

    # bpPayRequest call for Mallat gateway
    def pay_request(self, params={}):
        data = dict(
            orderId=params['orderId'],
            amount=params['amount'],
            localDate=params['localDate'],
            localTime=params['localTime'],
            additionalData=params['additionalData'],
            callBackUrl=params['callBackUrl'],
            payerId=params['payerId']
        )
        return self._bp_request(data, 'bpPayRequest')

    # bpVerifyRequest call for Mallat gateway
    def verify_request(self, params):
        return self._bp_request(self._bp_default_params(params), 'bpVerifyRequest')

    # bpSettleRequest call for Mallat gateway
    def settle_request(self, params):
        return self._bp_request(self._bp_default_params(params), 'bpSettleRequest')

    # bpInquiryRequest call for Mallat gateway
    def inquiry_request(self, params):
        return self._bp_request(self._bp_default_params(params), 'bpInquiryRequest')

    # bpReversalRequest call for Mallat gateway
    def reversal_request(self, params):
        return self._bp_request(self._bp_default_params(params), 'bpReversalRequest')

    def behpardakht_form_generate_values(self, values):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        behpardakht_tx_values = dict(values)

        order_reference = values.get('reference')
        additionalData = _('Customer Info: partner_id (%s), partner_name (%s)') % (values.get('partner_id'), values.get('partner_name'))
        transaction = self.env['payment.transaction'].search([('reference', '=', order_reference), ('state', '=', 'draft')], limit=1)

        currency_obj = values.get('currency')
        amount_value = int(values.get('amount'))
        if currency_obj.name == 'IRR':
            amount = amount_value
        elif currency_obj.name == 'IRT':
            amount = amount_value * 10
        else:
            error_msg = 'Currency: data error: Invalid Currency'
            _logger.info(error_msg)  # debug
            raise ValidationError(error_msg)

        data = {
            'orderId': transaction.id,
            'amount': amount,
            'localDate': datetime.datetime.now().strftime('%Y%m%d'),
            'localTime': datetime.datetime.now().strftime('%H%M%S'),
            'additionalData': additionalData,
            'callBackUrl': urls.url_join(base_url, BehpardakhtController._accept_url),
            'payerId': 0,
        }
        # Pay Request Method Call
        result = self.pay_request(data)
        if result is not None:
            result_list = result.split(',')
            if result_list[0] == '0':
                temp_behpardakht_tx_values = {'RefId': result_list[1]}
                behpardakht_tx_values.update(temp_behpardakht_tx_values)
                self.env['payment.transaction'].sudo()._behpardakht_set_tx_RefId(values.get('reference'), result_list[1])
            else:
                error_msg = _('Behpardakht: feedback error: ') + BEHPARDAKHT_ERROR_MAP.get(result_list[0])
                _logger.info(error_msg)  # debug
                raise ValidationError(error_msg)

        return behpardakht_tx_values

    def behpardakht_get_wsdl_url(self):
        self.ensure_one()
        environment = 'prod' if self.state == 'enabled' else 'test'
        return self._get_behpardakht_urls(environment)['behpardakht_wsdl_url']

    def behpardakht_get_form_action_url(self):
        self.ensure_one()
        environment = 'prod' if self.state == 'enabled' else 'test'
        return self._get_behpardakht_urls(environment)['behpardakht_order_url']


class PaymentTxBehpardakht(models.Model):
    _inherit = 'payment.transaction'

    behpardakht_refid = fields.Char(string='Behpardakht Reference Id', readonly=True, help='Reference of the TX as stored in the acquirer database')

    @api.model
    def _behpardakht_set_tx_RefId(self, reference, RefId):
        tx = self.search([('reference', '=', reference)])
        if tx:
            tx.behpardakht_refid = RefId
        return

    def _behpardakht_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        if self.behpardakht_refid and data.get('RefId').upper() != self.behpardakht_refid.upper():
            invalid_parameters.append(('RefId', data.get('REFID'), self.behpardakht_refid))
        return invalid_parameters

    @api.model
    def _behpardakht_form_get_tx_from_data(self, data):
        """ Given a data dict coming from behpardakht, verify it and
        find the related transaction record. """
        RefId = data.get('RefId', '')
        ResCode = data.get('ResCode', '')
        SaleOrderId = data.get('SaleOrderId', '')

        if not SaleOrderId or not ResCode or not RefId:
            error_msg = 'Behpardakht: received data with missing SaleOrderId (%s) or RefId (%s) or ResCode (%s)' % (SaleOrderId, RefId, ResCode)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        tx = self.env['payment.transaction'].search([('behpardakht_refid', '=', RefId)])
        if not tx or len(tx) > 1:
            error_msg = 'Behpardakht: received data for reference %s' % RefId
            if not tx:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'

            _logger.info(error_msg)
            raise ValidationError(error_msg)

        return tx

    def _behpardakht_form_validate(self, data):
        status = data.get('ResCode', None)
        SaleOrderId = data.get('SaleOrderId', '')
        SaleReferenceId = data.get('SaleReferenceId', '')

        former_tx_state = self.state

        date = fields.date.today()
        res = {}

        if status == '0':
            behpardakht_acquirer_obj = self.env['payment.acquirer'].search([('provider', '=', 'behpardakht')])
            data = {
                'orderId': int(SaleOrderId),
                'saleOrderId': int(SaleOrderId),
                'saleReferenceId': int(SaleReferenceId),
            }

            result = behpardakht_acquirer_obj.verify_request(data)
            status = result.split(',')[0] if result is not None else None
            if status == '0':
                result = behpardakht_acquirer_obj.settle_request(data)
                status = result.split(',')[0] if result is not None else None
                if status == '0':
                    self.acquirer_reference = SaleReferenceId
                    res.update(date=date)
                    self._set_transaction_done()
                    if self.state == 'done' and self.state != former_tx_state:
                        _logger.info('Validated Behpardakht payment for tx %s: set as done' % self.reference)
                        return self.write(res)
                    return True

        if status is not None:
            error = _('%s Transaction Error: (%s) %s') % (self.reference, status, BEHPARDAKHT_ERROR_MAP.get(status))
        else:
            error = _('Received unrecognized status for Behpardakht payment ') + self.reference

        self._set_transaction_error(error)
        return True
