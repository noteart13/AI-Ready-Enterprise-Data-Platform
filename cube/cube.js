module.exports = {
  telemetry: false,
  checkAuth: (req, auth) => {
    // Extract Security Context for Row-Level Security
    const token = auth;
    let securityContext = {
      tenant_id: "GLOBAL_TENANT",
      role: "admin",
      department: "EXECUTIVE",
      security_clearance: "RESTRICTED"
    };

    if (req.headers && req.headers['x-tenant-id']) {
      securityContext.tenant_id = req.headers['x-tenant-id'];
    }
    if (req.headers && req.headers['x-role']) {
      securityContext.role = req.headers['x-role'];
    }
    if (req.headers && req.headers['x-security-clearance']) {
      securityContext.security_clearance = req.headers['x-security-clearance'];
    }

    return {
      securityContext
    };
  },
  queryRewrite: (query, { securityContext }) => {
    // Enforce Row-Level Security: Automatically append tenant_id filter if not admin
    if (securityContext.tenant_id && securityContext.tenant_id !== "GLOBAL_TENANT") {
      query.filters = query.filters || [];
      query.filters.push({
        member: 'Orders.tenantId',
        operator: 'equals',
        values: [securityContext.tenant_id]
      });
    }
    return query;
  }
};
