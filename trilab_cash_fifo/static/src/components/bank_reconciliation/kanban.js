/** @odoo-module **/
import { patch } from "@web/core/utils/patch"

import { BankRecKanbanController } from "@account_accountant/components/bank_reconciliation/kanban"

patch(BankRecKanbanController.prototype, {
    async xActionPostMove() {
        await this.execProtectedBankRecAction(async () => {
            await this.withNewState(async newState => {
                await this._xActionPostMove(newState)
            })
        })
    },

    async _xLoadLine(newState) {
        const counter = newState.counter
        await this.model.root.load()
        newState.counter = counter
        newState.__kanbanNotify = true
    },

    async _xActionPostMove(newState) {
        const { return_todo_command: result } = await this.onchange(newState, "x_post_move")
        if (result.done) {
            this.incrementReconCounter()
            await this._xLoadLine(newState)
        }
        return result
    },
})
