# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

import requests
from werkzeug import urls

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from .. import const


_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("chargily", "Chargily")], ondelete={"chargily": "set default"}
    )

    chargily_public_token = fields.Char(
        string="Chargily public token",
        required_if_provider="chargily",
        groups="base.group_system",
    )

    chargily_secret_token = fields.Char(
        string="Chargily secret token",
        required_if_provider="chargily",
        groups="base.group_system",
    )

    # === BUSINESS METHODS === #

    def _get_supported_currencies(self):
        """Override of `payment` to return the supported currencies."""
        supported_currencies = super()._get_supported_currencies()
        if self.code == "chargily":
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _chargily_get_api_url(self):
        """Return the API URL according to the provider state.

        Note: self.ensure_one()

        :return: The API URL
        :rtype: str
        """
        self.ensure_one()

        if self.state == "enabled":
            return "https://pay.chargily.net/api/v2/"
        else:
            return "https://pay.chargily.net/test/api/v2/"

    # TODO: here
    def _chargily_make_request(self, endpoint, payload=None, method="POST"):
        """Make a request to Chargily API at the specified endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request.
        :param dict payload: The payload of the request.
        :param str method: The HTTP method of the request.
        :return The JSON-formatted content of the response.
        :rtype: dict
        :raise ValidationError: If an HTTP error occurs.
        """
        self.ensure_one()

        chargily_url = self._chargily_get_api_url()
        _logger.info(chargily_url)
        url = urls.url_join(chargily_url, endpoint)
        _logger.info(f"============================> {url}")

        headers = {"Authorization": f"Bearer {self.chargily_secret_token}"}
        try:
            if method == "GET":
                response = requests.get(
                    url, params=payload, headers=headers, timeout=10
                )
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError:
                    _logger.exception(
                        "Invalid API request at %s with data:\n%s",
                        url,
                        pprint.pformat(payload),
                    )
                    try:
                        response_content = response.json()
                        _logger.info(response_content)
                        error_code = str(response_content.get("errors"))
                        error_message = response_content.get("message")
                        raise ValidationError(
                            "Chargily: "
                            + _(
                                "The communication with the API failed. Chargily gave us the"
                                " following information: '%s' (code %s)",
                                error_message,
                                error_code,
                            )
                        )
                    except (
                        ValueError
                    ):  # The response can be empty when the access token is wrong.
                        raise ValidationError(
                            "Chargily: "
                            + _(
                                "The communication with the API failed. The response is empty. Please"
                                " verify your access token."
                            )
                        )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Unable to reach endpoint at %s", url)
            raise ValidationError(
                "Chargily: " + _("Could not establish the connection to the API.")
            )
        return response.json()

    def _get_default_payment_method_codes(self):
        """Override of `payment` to return the default payment method codes."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != "chargily":
            return default_codes
        return const.DEFAULT_PAYMENT_METHODS_CODES
