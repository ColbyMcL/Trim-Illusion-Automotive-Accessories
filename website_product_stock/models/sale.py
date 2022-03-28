# -*- coding: utf-8 -*-


from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def get_section_data(self):
        section = {}
        if self.order_line:
            section_name = False
            section_total = 0
            for each in self.order_line:
                if each.display_type and each.display_type == 'line_section':
                    section[each.name] = 0
                    section_name = each.name
                    section_total = 0
                if section_name and section_name in section:
                    section[section_name] = section[section_name] + each.price_subtotal
        return section