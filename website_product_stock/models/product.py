
from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def product_qty_get(self):
        warehouse_line = []
        for warehouse_id in self.env['stock.warehouse'].sudo().search([]):
            ctx = {'warehouse': warehouse_id.id, 'product_id': self}
            stock = self.with_context(ctx).sudo()._compute_quantities_dict(
                lot_id=False, owner_id=False, package_id=False,
                from_date=False, to_date=False)
            if stock:
                warehouse_line.append({
                    'warehouse_id': warehouse_id.id,
                    'warehouse_name': warehouse_id.name,
                    'qty': stock.get(self.id).get(
                        'qty_available'),
                    'incoming_qty': stock.get(self.id).get(
                        'incoming_qty'),
                    'outgoing_qty': stock.get(self.id).get(
                        'outgoing_qty'),
                    'forecasted_qty': stock.get(self.id).get(
                        'free_qty')
                })
        return warehouse_line
