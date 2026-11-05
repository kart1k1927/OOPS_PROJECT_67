//admin dashboard

export async function getDashboardMetrics() {
  const [totalRes, openRes, criticalRes, resolvedRes, slaBreachedRes] = await Promise.all([
    supabase.from('incidents').select('id', { count: 'exact', head: true }),
    supabase.from('incidents').select('id', { count: 'exact', head: true }).not('status', 'in', '("RESOLVED","CLOSED")'),
    supabase.from('incidents').select('id', { count: 'exact', head: true }).eq('priority', 'P1'),
    supabase.from('incidents').select('id', { count: 'exact', head: true }).eq('status', 'RESOLVED'),
    supabase.from('incidents').select('id', { count: 'exact', head: true }).or('response_sla_breached.eq.true,resolution_sla_breached.eq.true')
  ]);

  return {
    totalIncidents: totalRes.count || 0,
    openIncidents: openRes.count || 0,
    criticalIncidents: criticalRes.count || 0,
    resolvedIncidents: resolvedRes.count || 0,
    slaViolations: slaBreachedRes.count || 0
  };
}

//technician workload

export async function getTechnicianWorkloadReport() {
  const { data, error } = await supabase
    .from('profiles')
    .select(`
      id,
      name,
      email,
      assigned_incidents:incidents!incidents_assigned_technician_id_fkey(id, status)
    `)
    .eq('role', 'TECHNICIAN');

  if (error) throw error;

  // Transform data to count active (non-closed) incidents per technician
  return data.map(tech => ({
    technicianId: tech.id,
    technicianName: tech.name,
    activeIncidentsCount: tech.assigned_incidents.filter(
      inc => inc.status !== 'CLOSED' && inc.status !== 'RESOLVED'
    ).length
  }));
}

//individual service report
export async function getServiceAnalysisReport() {
  const { data, error } = await supabase
    .from('services')
    .select(`
      id,
      name,
      business_criticality,
      incidents(id)
    `);

  if (error) throw error;

  return data.map(service => ({
    serviceId: service.id,
    serviceName: service.name,
    businessCriticality: service.business_criticality,
    totalIncidents: service.incidents.length
  }));
}

//fetches incidents breached or at risk
export async function getSLABreachMonitor() {
  const { data, error } = await supabase
    .from('incidents')
    .select(`
      id,
      priority,
      status,
      response_deadline_at,
      resolution_deadline_at,
      response_sla_breached,
      resolution_sla_breached,
      assigned_technician:profiles!incidents_assigned_technician_id_fkey(name),
      services(name)
    `)
    .or('response_sla_breached.eq.true,resolution_sla_breached.eq.true')
    .not('status', 'in', '("CLOSED")');

  if (error) throw error;
  return data;
}

//incident logs
export async function getIncidentAuditLogs(incidentId?: string) {
  let query = supabase
    .from('audit_logs')
    .select(`
      id,
      action,
      previous_state,
      new_state,
      description,
      timestamp,
      user:profiles (name, role)
    `)
    .order('timestamp', { ascending: false });

  if (incidentId) {
    query = query.eq('incident_id', incidentId);
  }

  const { data, error } = await query;
  if (error) throw error;
  return data;
}

