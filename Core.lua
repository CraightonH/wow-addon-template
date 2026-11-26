local addonName, addon = ...

-- Keep runtime state in the private addon namespace.
local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:SetScript("OnEvent", function(_, _, loadedName)
    if loadedName ~= addonName then return end
    ExampleAddonDB = ExampleAddonDB or { schemaVersion = 1 }
    addon.db = ExampleAddonDB
    frame:UnregisterEvent("ADDON_LOADED")
end)
