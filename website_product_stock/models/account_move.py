# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def get_section_data(self):
        section = {}
        if self.invoice_line_ids:
            section_name = False
            section_total = 0
            for each in self.invoice_line_ids:
                if each.display_type and each.display_type == 'line_section':
                    section[each.name] = 0
                    section_name = each.name
                    section_total = 0
                if section_name and section_name in section:
                    section[section_name] = section[section_name] + each.price_subtotal
        return section