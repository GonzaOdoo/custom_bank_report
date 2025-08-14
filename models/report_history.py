import io
import xlsxwriter
import base64
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)
class PendingPurchases(models.TransientModel):
    _name ='bank.custom.report'
    _description = 'Pedidos Pendientes'

    name = fields.Char('Nombre',compute='_compute_name')
    journal_id = fields.Many2one('account.journal','Diario',domain=[('type', '=', 'bank')])
    account_id = fields.Many2one('account.account',string='Proveedor',related='journal_id.default_account_id')
    date_start = fields.Date(
        'Desde',
        default=lambda self: fields.Date.today().replace(month=1, day=1)
    )
    date_end = fields.Date(
        'Hasta',
        default=fields.Date.today
    )
    order_list = fields.Many2many('bank.custom.report.line',string='Líneas pendientes',compute='_compute_list')

    @api.depends('journal_id')
    def _compute_name(self):
        for record in self:
            if record.journal_id:
                record.name = f"Reporte Bancos: {record.journal_id.name}"
            else:
                record.name = "Reporte Bancos"


    
    @api.depends('journal_id', 'date_start', 'date_end')
    def _compute_list(self):
        Line = self.env['bank.custom.report.line']
        for record in self:
            # === Limpiar líneas anteriores ===
            if record.order_list:
                record.order_list.unlink()  # Elimina los registros físicos
            record.order_list = [Command.clear()]
            if not record.journal_id or not record.date_start:
                record.order_list = [Command.clear()]
                continue
            # 1. Calcular balance inicial (hasta el día anterior a date_start)
            balance_inicial = 0.0
            if record.date_start:
                domain_inicial = [
                    ('parent_state', '=', 'posted'),
                    ('account_id', '=', record.account_id.id),
                    ('date', '<', record.date_start),
                ]
                move_lines_iniciales = self.env['account.move.line'].search(domain_inicial, order='date asc')
                for line in move_lines_iniciales:
                    balance_inicial += line.debit - line.credit
    
            # 2. Limpiar líneas anteriores
            line_ids = []
    
            # 3. Crear línea de balance inicial
            if balance_inicial != 0.0 or True:  # siempre mostrar, incluso si es 0
                initial_line = Line.create({
                    'name': 'Balance Inicial',
                    'date': record.date_start - timedelta(days=1),
                    'debit': balance_inicial if balance_inicial > 0 else 0.0,
                    'credit': -balance_inicial if balance_inicial < 0 else 0.0,
                    'balance': balance_inicial,
                    'is_initial_balance': True,
                    'move_id': False,
                    'is_grouped': False,
                    'journal_id': record.journal_id.id,
                })
                line_ids.append(initial_line.id)
    
            # 4. Ahora procesar movimientos dentro del rango (igual que antes, con agrupación)
            domain = [
                ('parent_state', '=', 'posted'),
                ('account_id', '=', record.account_id.id),
            ]
            if record.date_start:
                domain.append(('date', '>=', record.date_start))
            if record.date_end:
                domain.append(('date', '<=', record.date_end))
    
            move_lines = self.env['account.move.line'].search(domain, order='date asc')
    
            grouped_data = {}
            sequence = 0
    
            for line in move_lines:
                ref = line.move_id.ref or False
                sequence += 1
                key = ref if ref else f"no_ref_{sequence}"
    
                if key not in grouped_data:
                    grouped_data[key] = {
                        'debit': 0.0,
                        'credit': 0.0,
                        'moves': self.env['account.move'],
                        'sequence': sequence,
                        'ref': ref,
                        'min_date': line.date,
                    }
                grouped_data[key]['debit'] += line.debit
                grouped_data[key]['credit'] += line.credit
                if line.date < grouped_data[key]['min_date']:
                    grouped_data[key]['min_date'] = line.date
                if line.move_id not in grouped_data[key]['moves']:
                    grouped_data[key]['moves'] |= line.move_id
    
            # 5. Crear líneas del rango con balance acumulado (partiendo del inicial)
            balance = balance_inicial  # ✅ empezamos desde el balance inicial
    
            for key, data in sorted(grouped_data.items(), key=lambda x: x[1]['min_date']):
                balance += data['debit'] - data['credit']
                is_grouped = len(data['moves']) > 1 and data['ref']
                move_id = False if is_grouped else data['moves'][:1].id
    
                new_line = Line.create({
                    'name': data['ref'] if is_grouped else (data['moves'][:1].name or "Sin nombre"),
                    'date': data['min_date'],
                    'debit': data['debit'],
                    'credit': data['credit'],
                    'balance': balance,
                    'move_id': move_id,
                    'is_grouped': is_grouped,
                    'ref': data['ref'],
                    'is_initial_balance': False,
                    'journal_id': record.journal_id.id,
                })
                line_ids.append(new_line.id)
    
            # 6. Asignar todas las líneas al campo m2m
            record.order_list = [Command.clear()]
            record.order_list = [Command.set(line_ids)]
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def generate_excel_report(self):
        self.ensure_one()
    
        # Crear archivo en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Reporte Bancario')
    
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'text_wrap': False
        })
    
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        amount_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        balance_format = workbook.add_format({'num_format': '#,##0.00', 'bold': True, 'border': 1})
    
        # Cabeceras
        headers = [
            'Fecha',
            'Descripción',
            'Referencia / Movimientos',
            'Débito',
            'Crédito',
            'Saldo'
        ]
    
        # Escribir cabeceras
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
    
        # Datos del reporte
        row = 1
        for line in self.order_list.sorted('date'):  # ordenar por fecha
            # Formato condicional para balance inicial
            is_initial = line.is_initial_balance
            cell_format = balance_format if is_initial else amount_format
    
            worksheet.write(row, 0, line.date, date_format)
            worksheet.write(row, 1, line.name, text_format)
    
            if line.is_grouped:
                ref_text = f"Grupo: {line.ref} ({line.move_count} movimientos)"
                worksheet.write(row, 2, ref_text, text_format)
            elif line.move_id:
                worksheet.write(row, 2, line.move_id.name, text_format)
            else:
                worksheet.write(row, 2, '', text_format)
    
            worksheet.write(row, 3, line.debit, amount_format)
            worksheet.write(row, 4, line.credit, amount_format)
            worksheet.write(row, 5, line.balance, cell_format)
            row += 1
    
        # Ajustar ancho de columnas
        worksheet.set_column('A:A', 12)  # Fecha
        worksheet.set_column('B:B', 25)  # Descripción
        worksheet.set_column('C:C', 25)  # Referencia
        worksheet.set_column('D:F', 15)  # Montos
    
        # Agregar totales al final (opcional: solo débito y crédito)
        if row > 1:
            total_debit = sum(line.debit for line in self.order_list if not line.is_initial_balance)
            total_credit = sum(line.credit for line in self.order_list if not line.is_initial_balance)
            final_balance = self.order_list[-1].balance if self.order_list else 0.0
    
            worksheet.write(row, 2, 'TOTALES', header_format)
            worksheet.write(row, 3, total_debit, amount_format)
            worksheet.write(row, 4, total_credit, amount_format)
            worksheet.write(row, 5, final_balance, balance_format)
    
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()
    
        # Nombre del archivo con fecha
        filename = f"Reporte_Bancario_{self.journal_id.name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
        # Crear adjunto
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
            'public': True,
        })
    
        # Retornar acción de descarga
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

class CustomReportLine(models.Model):
    _name = 'bank.custom.report.line'

    # Campo requerido para los campos Monetarios
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )
    date = fields.Date('Fecha')
    move_id = fields.Many2one('account.move',string="Asiento")
    is_grouped = fields.Boolean('Agrupado')
    is_initial_balance = fields.Boolean('Balance inicial')
    ref = fields.Char('Referencia')  # para filtrar luego
    name = fields.Char('Etiqueta')
    debit = fields.Monetary('Debito')
    credit = fields.Monetary('Credito')
    balance = fields.Monetary('Balance')
    move_count = fields.Integer('Cantidad de Asientos', compute='_compute_move_count')
    journal_id = fields.Many2one('account.journal','Diario',domain=[('type', '=', 'bank')])
    account_id = fields.Many2one('account.account',string='Proveedor',related='journal_id.default_account_id')
    
    @api.depends('ref')
    def _compute_move_count(self):
        for line in self:
            if line.is_grouped and line.ref:
                count = self.env['account.move'].search_count([('ref', '=', line.ref)])
                line.move_count = count
            else:
                line.move_count = 1


    def action_view_moves(self):
        self.ensure_one()
        
        if self.is_grouped and self.ref:
            moves = self.env['account.move'].search([('ref', '=', self.ref),('journal_id.default_account_id','=',self.account_id.id)])
            return {
                'type': 'ir.actions.act_window',
                'name': f'Movimientos con referencia: {self.ref}',
                'res_model': 'account.move',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', moves.ids)],
                'context': {'create': False, 'edit': False},
                'target': 'current',
            }
        elif self.move_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Asiento Contable',
                'res_model': 'account.move',
                'res_id': self.move_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
            