from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)
class PendingPurchases(models.Model):
    _inherit ='account.journal'

    def action_open_bank_custom_report(self):
        self.ensure_one()

        # Obtener el primer día del mes actual
        today = fields.Date.today()
        date_start = today.replace(day=1)  # Primer día del mes

        return {
            'name': f'Reporte Bancario: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'bank.custom.report',
            'view_mode': 'form',
            'target': 'self',
            'context': {
                'default_journal_id': self.id,
                'default_date_start': date_start,
                'default_date_end': today,
            },
            # Opcional: si tienes una vista personalizada
            # 'view_id': self.env.ref('tu_modulo.view_bank_report_form').id,
        }

    @api.model
    def open_from_bank(self, id):
        """
        Método llamado vía ORM RPC. self no se usa, pero Odoo lo pasa.
        """
        journal = self.browse(id)
        if not journal.exists():
            raise ValueError("Diario no encontrado")
    
        today = fields.Date.today()
        date_start = today.replace(day=1)
    
        return {
            'name': f'Reporte Bancario: {journal.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'bank.custom.report',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_journal_id': id,
                'default_date_start': date_start,
                'default_date_end': today,
            },
            'views': [[False, 'form']],
        }



    