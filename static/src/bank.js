/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { BankRecGlobalInfo } from "@account_accountant/components/bank_reconciliation/global_info";

patch(BankRecGlobalInfo.prototype, {
    /**
     * Nuevo método que llama al backend y abre la acción
     */
    async actionOpenCustomReport() {
        const action = await this.env.services.orm.call(
            "account.journal",
            "open_from_bank",
            [this.props.journalId]  // pasar el ID del diario
        );
        this.env.services.action.doAction(action);
    }
});