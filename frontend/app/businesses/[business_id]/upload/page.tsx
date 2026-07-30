'use client'
import { useState } from 'react'
import { useParams } from 'next/navigation'
import { uploadApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import { Upload, FileCheck, AlertCircle, CheckCircle2 } from 'lucide-react'

export default function UploadPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [datasetType, setDatasetType] = useState<string>('products')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [report, setReport] = useState<any>(null)
  const [error, setError] = useState<string>('')

  const handleUpload = async () => {
    if (!file) return
    setUploading(true); setError(''); setReport(null)
    try {
      const res = await uploadApi.upload(bizId, datasetType, file)
      setReport(res)
    } catch (e: any) {
      setError(e.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page-container">
      <PageHeader
        badge="Data Pipeline"
        title="Data Upload & Ingestion"
        description="Upload CSV or Excel files for Products, Purchases, or Sales. Business ID is automatically injected server-side."
      />

      <div className="grid-2 section-gap fade-up">
        {/* Upload Form */}
        <div className="card dot-matrix-subtle" style={{ padding: '1.5rem' }}>
          <h3 className="text-title" style={{ marginBottom: '1.25rem' }}>Upload New File</h3>

          <div style={{ marginBottom: '1.25rem' }}>
            <label className="label">Dataset Type</label>
            <select
              className="input"
              value={datasetType}
              onChange={e => setDatasetType(e.target.value)}
            >
              <option value="products">Products Master (Catalog)</option>
              <option value="purchases">Purchases (Inflows)</option>
              <option value="sales">Sales (Outflows)</option>
            </select>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label className="label">Select File (.csv, .xlsx)</label>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              className="input"
              onChange={e => setFile(e.target.files?.[0] || null)}
            />
          </div>

          {error && <p style={{ color: '#E05555', fontSize: '0.8125rem', marginBottom: '1rem' }}>{error}</p>}

          <button
            className="btn btn-primary"
            style={{ width: '100%', height: 42 }}
            onClick={handleUpload}
            disabled={!file || uploading}
          >
            <Upload size={16} /> {uploading ? 'Processing & Validating…' : 'Upload & Validate'}
          </button>
        </div>

        {/* Quality Report Results */}
        <div className="card" style={{ padding: '1.5rem' }}>
          <h3 className="text-title" style={{ marginBottom: '1.25rem' }}>Data Quality Report</h3>

          {!report ? (
            <p className="text-small" style={{ color: 'var(--text-muted)' }}>
              Select a file and click upload to generate a data quality report.
            </p>
          ) : (
            <div>
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                <div style={{ padding: '0.75rem 1rem', background: 'rgba(58,143,95,0.15)', borderRadius: 8, flex: 1 }}>
                  <p className="text-xs" style={{ color: '#4CAF7D', margin: 0 }}>Accepted</p>
                  <p style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>{report.rows_accepted} rows</p>
                </div>
                <div style={{ padding: '0.75rem 1rem', background: 'rgba(161,51,51,0.15)', borderRadius: 8, flex: 1 }}>
                  <p className="text-xs" style={{ color: '#E05555', margin: 0 }}>Rejected</p>
                  <p style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>{report.rows_rejected} rows</p>
                </div>
              </div>

              {report.warnings?.length > 0 && (
                <div>
                  <p className="text-label" style={{ color: 'var(--gold)', marginBottom: '0.5rem' }}>Validation Warnings</p>
                  <div style={{ maxHeight: 180, overflowY: 'auto', background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: 8 }}>
                    {report.warnings.map((w: string, idx: number) => (
                      <p key={idx} className="text-xs" style={{ margin: '0 0 4px', color: 'var(--text-secondary)' }}>• {w}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
