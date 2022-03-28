# -*- coding: utf-8 -*-

from werkzeug.exceptions import Forbidden, NotFound
import logging
from odoo import fields, http, SUPERUSER_ID, tools, _
from odoo.http import request
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.website.models.ir_http import sitemap_qs2dom
from odoo.addons.website.controllers.main import QueryURL
from odoo.addons.website.models import ir_http
from odoo.osv import expression
_logger = logging.getLogger(__name__)

ppg = 20


class TableComputeStock(object):

    def __init__(self):
        self.table = {}

    def _check_place_stock(self, posx, posy, sizex, sizey, ppr):
        res = True
        for y in range(sizey):
            for x in range(sizex):
                if posx + x >= ppr:
                    res = False
                    break
                row = self.table.setdefault(posy + y, {})
                if row.setdefault(posx + x) is not None:
                    res = False
                    break
            for x in range(ppr):

                self.table[posy + y].setdefault(x, None)
        return res

    def process_stock_product(self, products, ppg=20, ppr=4):
        # Compute products positions on the grid
        minpos = 0
        index = 0
        maxy = 0
        x = 1
        y = 1
        for p in products:
            # x = min(max(p.website_size_x, 1), ppr)
            # y = min(max(p.website_size_y, 1), ppr)
            if index >= ppg:
                x = y = 1

            pos = minpos
            while not self._check_place_stock(pos % ppr, pos // ppr, x, y, ppr):
                pos += 1
            # if 21st products (index 20) and the last line is full (ppr products in it), break
            # (pos + 1.0) / ppr is the line where the product would be inserted
            # maxy is the number of existing lines
            # + 1.0 is because pos begins at 0, thus pos 20 is actually the 21st block
            # and to force python to not round the division operation
            if index >= ppg and ((pos + 1.0) // ppr) > maxy:
                break

            if x == 1 and y == 1:   # simple heuristic for CPU optimization
                minpos = pos // ppr

            for y2 in range(y):
                for x2 in range(x):
                    self.table[(pos // ppr) + y2][(pos % ppr) + x2] = False
            self.table[pos // ppr][pos % ppr] = {
                'product': p, 'x': x, 'y': y,
                # 'ribbon': p.website_ribbon_id,
            }
            if index <= ppg:
                maxy = max(maxy, y + (pos // ppr))
            index += 1

        # Format table according to HTML needs
        rows = sorted(self.table.items())
        rows = [r[1] for r in rows]
        for col in range(len(rows)):
            cols = sorted(rows[col].items())
            x += len(cols)
            rows[col] = [r[1] for r in cols if r[1]]

        return rows


class WebsiteSaleStock(http.Controller):

    def sitemap_shop_stock(env, rule, qs):
        if not qs or qs.lower() in '/shop/stock':
            yield {'loc': '/shop/stock'}

        Category = env['product.public.category']
        dom = sitemap_qs2dom(qs, '/shop/stock//category', Category._rec_name)
        dom += env['website'].get_current_website().website_domain()
        for cat in Category.search(dom):
            loc = '/shop/stock/category/%s' % slug(cat)
            if not qs or qs.lower() in loc:
                yield {'loc': loc}

    def _get_search_domain_stock(self, search, category, attrib_values, search_in_description=True):
        domains = []
        if search:
            for srch in search.split(" "):
                subdomains = [
                    [('name', 'ilike', srch)],
                    [('product_variant_ids.default_code', 'ilike', srch)]
                ]
                if search_in_description:
                    subdomains.append([('description', 'ilike', srch)])
                    subdomains.append([('description_sale', 'ilike', srch)])
                domains.append(expression.OR(subdomains))

        if category:
            domains.append([('public_categ_ids', 'child_of', int(category))])

        if attrib_values:
            attrib = None
            ids = []
            for value in attrib_values:
                if not attrib:
                    attrib = value[0]
                    ids.append(value[1])
                elif value[0] == attrib:
                    ids.append(value[1])
                else:
                    domains.append([('attribute_line_ids.value_ids', 'in', ids)])
                    attrib = value[0]
                    ids = [value[1]]
            if attrib:
                domains.append([('attribute_line_ids.value_ids', 'in', ids)])

        return expression.AND(domains)

    def _get_search_order(self, post):
        # OrderBy will be parsed in orm and so no direct sql injection
        # id is added to be sure that order is a unique sort key
        order = post.get('order') or 'id ASC'
        return '%s, id desc' % order

    @http.route([
            '''/shop/stock''',
            '''/shop/stock/page/<int:page>''',
            '''/shop/stock/category/<model("product.public.category"):category>''',
            '''/shop/stock/category/<model("product.public.category"):category>/page/<int:page>'''
        ], type='http', auth="public", website=True, sitemap=sitemap_shop_stock)
    def shopstock(self, page=0, category=None, search='', ppg=False, **post):
            add_qty = int(post.get('add_qty', 1))
            if ppg:
                try:
                    ppg = int(ppg)
                    post['ppg'] = ppg
                except ValueError:
                    ppg = False
            if not ppg:
                ppg = 20

            ppr = 4

            attrib_list = request.httprequest.args.getlist('attrib')
            attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
            attributes_ids = {v[0] for v in attrib_values}
            attrib_set = {v[1] for v in attrib_values}

            domain = self._get_search_domain_stock(search, category, attrib_values)

            keep = QueryURL('/shop/stock', category=category and int(category), search=search, attrib=attrib_list, order=post.get('order'))

            url = "/shop/stock"
            if search:
                post["search"] = search
            if attrib_list:
                post['attrib'] = attrib_list

            Product = request.env['product.product'].sudo().with_context(bin_size=True)
            search_product = Product.sudo().search(domain, order=self._get_search_order(post))
            website_domain = request.website.website_domain()
            categs_domain = [('parent_id', '=', False)] + website_domain
            # if search:
            #     search_categories = Category.search([('product_tmpl_ids', 'in', search_product.ids)] + website_domain).parents_and_self
            #     categs_domain.append(('id', 'in', search_categories.ids))
            # else:
            #     search_categories = Category
            # categs = Category.search(categs_domain)
            #
            # if category:
            #     url = "/shop/category/%s" % slug(category)

            product_count = len(search_product)
            pager = request.website.pager(url=url, total=product_count, page=page, step=ppg, scope=7, url_args=post)
            offset = pager['offset']
            products = search_product[offset: offset + ppg]

            values = {
                'search': search,
                'category': category,
                'attrib_values': attrib_values,
                'attrib_set': attrib_set,
                'pager': pager,
                # 'pricelist': pricelist,
                'add_qty': add_qty,
                'products': products,
                'search_count': product_count,  # common for all searchbox
                'bins': TableComputeStock().process_stock_product(products, ppg, ppr),
                'ppg': ppg,
                'ppr': ppr,
                # 'categories': categs,
                # 'attributes': attributes,
                'keep': keep,
                # 'search_categories_ids': search_categories.ids,
                # 'layout_mode': layout_mode,
            }
            if category:
                values['main_object'] = category
            return request.render("website_product_stock.stock_product", values)

    @http.route(['/shop/stock/<string:product>'], type='http', auth="public", website=True, sitemap=True)
    def productstock(self, product, category='', search='', **kwargs):
        product = request.env['product.product'].sudo().browse(int(product))
        return request.render("website_product_stock.product", self._prepare_product_values_stock(product, search, **kwargs))

    def _prepare_product_values_stock(self, product, search, **kwargs):
        add_qty = int(kwargs.get('add_qty', 1))

        product_context = dict(request.env.context, quantity=add_qty,
                               active_id=product.id,
                               partner=request.env.user.partner_id)

        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attrib_set = {v[1] for v in attrib_values}

        keep = QueryURL('/shop/stock', search=search, attrib=attrib_list)

        # Needed to trigger the recently viewed product rpc
        view_track = request.website.viewref("website_product_stock.product").track
        return {
            'search': search,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'keep': keep,
            'main_object': product,
            'product': product,
            'add_qty': add_qty,
            'view_track': view_track,

        }
