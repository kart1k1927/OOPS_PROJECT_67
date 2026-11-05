//view assigned incidents
export async function getTechnicianQueue(technicianId: string) {
  const { data, error } = await supabase
    .from('incidents')
    .select(`
      id,
      category,
      description,
      priority,
      status,
      response_deadline_at,
      resolution_deadline_at,
      response_sla_breached,
      resolution_sla_breached,
      created_at,
      services (name),
      reporter:profiles!incidents_reporter_id_fkey (name, email)
    `)
    .eq('assigned_technician_id', technicianId)
    .not('status', 'in', '("RESOLVED","CLOSED")')
    .order('priority', { ascending: true })
    .order('created_at', { ascending: true });

  if (error) throw error;
  return data;
}

//acknolwedge incidents
export async function acknowledgeIncident(incidentId: string) {
  const now = new Date().toISOString();
  
  const { data, error } = await supabase
    .from('incidents')
    .update({
      status: 'ACKNOWLEDGED',
      acknowledged_at: now,
      responded_at: now,
      updated_at: now
    })
    .eq('id', incidentId)
    .select()
    .single();

  if (error) throw error;
  return data;
}

//add investigation notes
export async function addTechnicianNote(payload: {
  incident_id: string;
  author_id: string;
  content: string;
  is_internal: boolean;
}) {
  const { data, error } = await supabase
    .from('incident_updates')
    .insert([
      {
        incident_id: payload.incident_id,
        author_id: payload.author_id,
        update_type: payload.is_internal ? 'INTERNAL_NOTE' : 'PUBLIC_RESPONSE',
        content: payload.content,
        is_internal: payload.is_internal
      }
    ])
    .select()
    .single();

  if (error) throw error;
  return data;
}

//resolve incidents
export async function resolveIncident(payload: {
  incident_id: string;
  resolution_text: string;
}) {
  const now = new Date().toISOString();

  const { data, error } = await supabase
    .from('incidents')
    .update({
      status: 'RESOLVED',
      resolution: payload.resolution_text,
      resolved_at: now,
      updated_at: now
    })
    .eq('id', payload.incident_id)
    .select()
    .single();

  if (error) throw error;
  return data;
}

