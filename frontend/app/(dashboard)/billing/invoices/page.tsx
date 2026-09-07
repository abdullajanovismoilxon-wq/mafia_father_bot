'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, FileText, Loader2 } from 'lucide-react';
import { Invoice } from '@/types';
import { billingService } from '@/services/billing.service';

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await billingService.invoices();
        setInvoices(Array.isArray(data) ? data : []);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-6 max-w-4xl">
      <Link href="/billing" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Billing Overview
      </Link>

      <div className="flex items-center gap-3">
        <FileText className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-xl font-bold text-white">Invoices & Receipts</h1>
          <p className="text-slate-400 text-sm">Downloadable invoices for past subscription payments</p>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-800/80">
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Invoice Number</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Issued Date</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Amount</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {invoices.map((inv) => (
                <tr key={inv.id} className="bg-slate-800/30 hover:bg-slate-800/60 transition">
                  <td className="px-4 py-3 font-mono text-xs text-white">{inv.invoice_number}</td>
                  <td className="px-4 py-3 text-slate-300">{new Date(inv.issued_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 font-bold text-white">${inv.amount} {inv.currency}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-emerald-900/30 text-emerald-400 border border-emerald-500/30">
                      {inv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {invoices.length === 0 && (
            <div className="text-center py-12 text-slate-500 text-sm">No invoices issued yet.</div>
          )}
        </div>
      )}
    </div>
  );
}
