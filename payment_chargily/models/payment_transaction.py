# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
from urllib.parse import quote as url_quote

from werkzeug import urls

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

from .. import const
from ..controllers.main import ChargilyController


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment` to return Chargily-specific rendering values.

        Note: self.ensure_one() from `_get_rendering_values`.

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "chargily":
            return res

        # Initiate the payment and retrieve the payment link data.
        payload = self._chargily_prepare_preference_request_payload()
        _logger.info(
            "Sending '/checkout/preferences' request for link creation:\n%s",
            pprint.pformat(payload),
        )

        response = self.provider_id._chargily_make_request(
            "checkouts", payload=payload
        )

        # save checkout id to use later in webhook and return endpoint
        self.provider_reference = response.get("id")
        _logger.info(
            "Received response from '/checkout/preferences' request:\n%s",
            pprint.pformat(response),
        )
        checkout_url = response.get("checkout_url")

        rendering_values = {
            "api_url": checkout_url,
        }

        # TODO: I might make it pending here.
        return rendering_values

    def _chargily_prepare_preference_request_payload(self):
        """Create the payload for the preference request based on the transaction values.

        :return: The request payload.
        :rtype: dict
        """
        webhook_base_url = "https://1862-41-107-138-189.ngrok-free.app/"
        base_url = self.provider_id.get_base_url()
        return_url = urls.url_join(base_url, ChargilyController._return_url)
        webhook_url = urls.url_join(
            webhook_base_url, f"{ChargilyController._webhook_url}"
        )  # Append the reference to identify the transaction from the webhook notification data.

        return {
            "amount": self.amount,
            "currency": self.currency_id.name.lower(),
            "payment_method": self.payment_method_code,
            "success_url": return_url,
            "failure_url": return_url,
            "webhook_endpoint": webhook_url,
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override of `payment` to find the transaction based on Chargily data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If inconsistent data were received.
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "chargily" or len(tx) == 1:
            return tx

        provider_reference = notification_data.get("data", {}).get("id")
        if not provider_reference:
            raise ValidationError(
                "Chargily: " + _("Received data with missing provider_reference.")
            )

        tx = self.search(
            [("provider_reference", "=", provider_reference), ("provider_code", "=", "chargily")]
        )
        if not tx:
            raise ValidationError(
                "Chargily: "
                + _("No transaction found matching provider_reference %s.", provider_reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Override of `payment` to process the transaction based on Chargily data.

        Note: self.ensure_one() from `_process_notification_data`

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data were received.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != "chargily":
            return

        # TODO: check and update payment method
        # if not payment_method:
        #     payment_method = self.env["payment.method"].search(
        #         [("code", "=", "unknown")], limit=1
        #     )
        # self.payment_method_id = payment_method or self.payment_method_id

        # Update the payment state.
        payment_status = notification_data.get("type")
        if not payment_status:
            raise ValidationError(
                "Chargily: " + _("Received data with missing status.")
            )


        if payment_status in const.TRANSACTION_STATUS_MAPPING["done"]:
            self._set_done()
        elif payment_status in const.TRANSACTION_STATUS_MAPPING["canceled"]:
            self._set_canceled()
        elif payment_status in const.TRANSACTION_STATUS_MAPPING["error"]:
            _logger.warning(
                "Received data for transaction with reference %s with status %s and error code: %s",
                self.reference,
                payment_status,
            )
            error_message = self._chargily_get_error_msg(payment_status)
            self._set_error(error_message)
        else:  # Classify unsupported payment status as the `error` tx state.
            _logger.warning(
                "Received data for transaction with reference %s with invalid payment status: %s",
                self.reference,
                payment_status,
            )
            self._set_error(
                "Chargily: "
                + _("Received data with invalid status: %s", payment_status)
            )

    @api.model
    def _chargily_get_error_msg(self, status_detail):
        """Return the error message corresponding to the payment status.

        :param str status_detail: The status details sent by the provider.
        :return: The error message.
        :rtype: str
        """
        return "Chargily: " + status_detail
