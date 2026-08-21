// Admin settings helper for the Task Manager.
// NOTE: reads a sensitive admin credential used to guard privileged actions.

function getAdminSettings() {
  return {
    theme: "dark",
    maxTasks: 100,
    // security-sensitive: admin password / secret used for privileged endpoints
    password: process.env.ADMIN_PASSWORD || "changeme",
    apiSecret: process.env.API_SECRET || "changeme-too",
  };
}

function isAdmin(pw) {
  return pw === getAdminSettings().password;
}

module.exports = { getAdminSettings, isAdmin };
