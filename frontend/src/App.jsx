import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  CheckCircle, 
  HardHat, 
  DollarSign, 
  Package, 
  RefreshCw, 
  Upload, 
  MapPin 
} from 'lucide-react';
import { scanVideo, getTickets, resolveTicket } from './services/api';

export default function App() {
  const [tickets, setTickets] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState(null);

  // Fetch initial ticket list from FastAPI backend
  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const data = await getTickets();
      if (Array.isArray(data)) {
        setTickets(data);
      }
    } catch (err) {
      console.error("Failed to fetch tickets:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // Handle video upload and processing
  const handleScanVideo = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    try {
      const result = await scanVideo(file);
      if (result) {
        setSummary(result.total_materials_and_cost);
        if (result.defects) {
          setTickets(result.defects);
        }
      }
    } catch (err) {
      console.error("Video scan failed:", err);
      alert("Error processing video. Check console for details.");
    } finally {
      setUploading(false);
    }
  };

  // Handle resolving a ticket
  const handleResolve = async (defectCode) => {
    try {
      await resolveTicket(defectCode);
      setTickets((prev) =>
        prev.map((t) =>
          t.defect_code === defectCode ? { ...t, status: 'RESOLVED' } : t
        )
      );
    } catch (err) {
      console.error("Failed to resolve ticket:", err);
    }
  };

  // Calculate high-level stats from current ticket list
  const criticalCount = tickets.filter((t) => t.urgency_level === 'CRITICAL').length;
  const openTickets = tickets.filter((t) => t.status === 'OPEN').length;
  const resolvedTickets = tickets.filter((t) => t.status === 'RESOLVED').length;

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6">
      {/* Header Bar */}
      <header className="flex justify-between items-center pb-6 mb-8 border-b border-slate-800">
        <div>
          <h1 className="text-3xl font-bold text-amber-500 flex items-center gap-2">
            <HardHat className="h-8 w-8 text-amber-500" />
            RoadGuard AI
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Automated Pothole Detection & Civil Repair Estimation
          </p>
        </div>
        <button
          onClick={fetchDashboardData}
          disabled={loading}
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-lg text-sm font-medium border border-slate-700 transition"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Data
        </button>
      </header>

      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 text-sm mb-2">
            <span>Total Active Defect Tickets</span>
            <AlertTriangle className="h-5 w-5 text-amber-400" />
          </div>
          <p className="text-3xl font-bold text-slate-100">{openTickets}</p>
          <p className="text-xs text-red-400 mt-1">{criticalCount} Urgent / Critical</p>
        </div>

        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 text-sm mb-2">
            <span>Est. Repair Budget</span>
            <DollarSign className="h-5 w-5 text-emerald-400" />
          </div>
          <p className="text-3xl font-bold text-slate-100">
            ₹{summary ? summary.estimated_cost_inr.toLocaleString('en-IN') : '0'}
          </p>
          <p className="text-xs text-slate-400 mt-1">Calculated via civil cost engine</p>
        </div>

        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 text-sm mb-2">
            <span>Asphalt Required</span>
            <Package className="h-5 w-5 text-blue-400" />
          </div>
          <p className="text-3xl font-bold text-slate-100">
            {summary ? summary.asphalt_volume_m3 : '0'} m³
          </p>
          <p className="text-xs text-blue-400 mt-1">
            ~{summary ? summary.bags_25kg : '0'} Bags (25kg)
          </p>
        </div>

        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 text-sm mb-2">
            <span>Repaired Tickets</span>
            <CheckCircle className="h-5 w-5 text-emerald-500" />
          </div>
          <p className="text-3xl font-bold text-emerald-400">{resolvedTickets}</p>
          <p className="text-xs text-slate-400 mt-1">Closed dispatch tickets</p>
        </div>
      </div>

      {/* Main Grid: Upload Video & Ticket Dispatch Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Upload Form Section */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700/60 shadow-lg h-fit">
          <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <Upload className="h-5 w-5 text-amber-500" />
            Scan Road Inspection Video
          </h2>
          <form onSubmit={handleScanVideo} className="space-y-4">
            <div className="border-2 border-dashed border-slate-600 rounded-lg p-6 text-center hover:border-amber-500 transition cursor-pointer">
              <input
                type="file"
                accept="video/*"
                onChange={(e) => setFile(e.target.files[0])}
                className="hidden"
                id="video-upload"
              />
              <label htmlFor="video-upload" className="cursor-pointer">
                <Upload className="h-8 w-8 text-slate-400 mx-auto mb-2" />
                <span className="text-sm text-slate-300 block font-medium">
                  {file ? file.name : "Click to select MP4 video"}
                </span>
                <span className="text-xs text-slate-500 block mt-1">
                  Supports .mp4 / .avi inspection footage
                </span>
              </label>
            </div>

            <button
              type="submit"
              disabled={!file || uploading}
              className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-bold py-2.5 rounded-lg transition flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <RefreshCw className="h-5 w-5 animate-spin" />
                  Running ML Pipeline...
                </>
              ) : (
                "Upload & Process Video"
              )}
            </button>
          </form>
        </div>

        {/* Ticket List Section */}
        <div className="lg:col-span-2 bg-slate-800 p-6 rounded-xl border border-slate-700/60 shadow-lg">
          <h2 className="text-lg font-semibold text-slate-200 mb-4">
            Municipal Repair Dispatch Queue
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900/60 text-slate-400 uppercase text-xs">
                <tr>
                  <th className="p-3">Ticket ID</th>
                  <th className="p-3">Urgency</th>
                  <th className="p-3">Asphalt Vol.</th>
                  <th className="p-3">Est. Cost (₹)</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {tickets.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="p-6 text-center text-slate-500">
                      No defects logged yet. Upload a video to scan for potholes!
                    </td>
                  </tr>
                ) : (
                  tickets.slice(0, 10).map((ticket) => (
                    <tr key={ticket.defect_code} className="hover:bg-slate-700/30 transition">
                      <td className="p-3 font-mono font-medium text-slate-200">
                        {ticket.defect_code}
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                            ticket.urgency_level === 'CRITICAL'
                              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                              : ticket.urgency_level === 'MEDIUM'
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          }`}
                        >
                          {ticket.urgency_level}
                        </span>
                      </td>
                      <td className="p-3">{ticket.asphalt_volume_m3} m³</td>
                      <td className="p-3 font-medium">
                        ₹{ticket.estimated_cost_inr ? ticket.estimated_cost_inr.toLocaleString('en-IN') : ticket.estimated_cost_usd}
                      </td>
                      <td className="p-3">
                        <span
                          className={`text-xs font-medium ${
                            ticket.status === 'RESOLVED' ? 'text-emerald-400' : 'text-amber-400'
                          }`}
                        >
                          {ticket.status}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        {ticket.status === 'OPEN' ? (
                          <button
                            onClick={() => handleResolve(ticket.defect_code)}
                            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3 py-1.5 rounded transition"
                          >
                            Resolve
                          </button>
                        ) : (
                          <span className="text-xs text-slate-500 flex items-center justify-end gap-1">
                            <CheckCircle className="h-3.5 w-3.5 text-emerald-500" /> Fixed
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}