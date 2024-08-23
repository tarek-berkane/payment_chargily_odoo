import json
import logging
import pprint

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.http import Request

from ..utils.validator import validate_signature

_logger = logging.getLogger(__name__)


class ChargilyController(http.Controller):
    _return_url = "/payment/chargily/return"
    _webhook_url = "/payment/chargily/webhook"

    @http.route(f"{_return_url}", type="http", methods=["GET"], auth="public")
    def chargily_return_from_checkout(self, **data):
        """Process the notification data sent by Chargily after redirection from checkout.
        :param dict data: The notification data.
        """
        # Handle the notification data.
        _logger.info(
            "Handling redirection from Chargily with data:\n%s",
            pprint.pformat(data),
        )


        checkout_id = data.get("checkout_id")
        _logger.info(f"================> {checkout_id}")
        if checkout_id != "null":
            request.env["payment.transaction"].sudo().search(
                [
                    ("provider_reference", "=", checkout_id),
                    ("provider_code", "=", "chargily"),
                ]
            )
        else:  # The customer cancelled the payment by clicking on the return button.
            pass  # Don't try to process this case because the payment id was not provided.

        # Redirect the user to the status page.
        return request.redirect("/payment/status")

    @http.route(
        f"{_webhook_url}", type="http", auth="public", methods=["POST"], csrf=False
    )
    def chargily_webhook(self, **_kwargs):
        """Process the notification data sent by Chargily to the webhook.

        :param str reference: The transaction reference embedded in the webhook URL.
        :param dict _kwargs: The extra query parameters.
        :return: An empty string to acknowledge the notification.
        :rtype: str
        """
        
        data = request.get_json_data()
        _logger.info(
            "Notification received from Chargily with data:\n%s",
            pprint.pformat(data),
        )
        if not data:
            return ""
    

        headers = request.httprequest.headers
        signature = headers.get("signature")
        payload = request.httprequest.get_data(as_text=True)

        scret_token = (
            request.env["payment.provider"]
            .sudo()
            .search([("code", "=", "chargily")], limit=1)
        )

        valide_notification = validate_signature(
            signature,
            payload,
            scret_token.chargily_secret_token,
        )

        _logger.info(f"Secret token: {scret_token.chargily_secret_token}")
        _logger.info(f"Signature: {signature}")
        _logger.info(f"valide_notification: {valide_notification}")

        if valide_notification:
            # Handle the notification data.
            try:
                request.env["payment.transaction"].sudo()._handle_notification_data(
                    "chargily", data
                )
            except (
                ValidationError
            ):  # Acknowledge the notification to avoid getting spammed.
                _logger.exception(
                    "Unable to handle the notification data; skipping to acknowledge"
                )
        else:
            _logger.info("Invalid notification signature.")

        
        return ""  # Acknowledge the notification.
