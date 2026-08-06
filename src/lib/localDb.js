// Shim → re-export from new SQLite-based DB layer (src/lib/db/)
// Kept for backward compatibility with existing imports.
export {
  getSettings, updateSettings, isCloudEnabled, getCloudUrl,
  getProviderConnections, getProviderConnectionById,
  createProviderConnection, updateProviderConnection,
  deleteProviderConnection, deleteProviderConnectionsByProvider,
  reorderProviderConnections, cleanupProviderConnections,
  getProviderNodes, getProviderNodeById,
  createProviderNode, updateProviderNode, deleteProviderNode,
  getProxyPools, getProxyPoolById,
  createProxyPool, updateProxyPool, deleteProxyPool,
  getApiKeys, getApiKeyById, createApiKey, updateApiKey, deleteApiKey, validateApiKey,
  getCombos, getComboById, getComboByName,
  createCombo, updateCombo, deleteCombo,
  getModelAliases, setModelAlias, deleteModelAlias,
  getCustomModels, addCustomModel, deleteCustomModel,
  getMitmAlias, setMitmAliasAll,
  getPricing, getPricingForModel, updatePricing, resetPricing, resetAllPricing,
  exportDb, importDb,
  // Automation (ported from AMRouter fork)
  listCodeBuddyAccounts, getCodeBuddyAccount, insertCodeBuddyAccount,
  bulkDeleteCodeBuddyAccounts, deleteCodeBuddyAccount,
  markCodeBuddyRunning, markCodeBuddySuccess, markCodeBuddyError, markCanvaEnrolled,
  createCodeBuddyJob, getCodeBuddyJob, updateCodeBuddyJobStatus, updateCodeBuddyJobResult,
  insertAmmailOtp, findLatestAmmailOtp, markAmmailOtpUsed,
  listAmmailOtps, getAmmailOtp, deleteAmmailOtp, deleteAmmailOtpsBulk,
} from "@/lib/db/index.js";
