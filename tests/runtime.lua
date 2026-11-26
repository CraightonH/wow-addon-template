-- A small lifecycle test. Add model tests as the addon gains real behavior.
local event, callback
local frame = {}
function frame:RegisterEvent(value) event = value end
function frame:UnregisterEvent(value)
    assert(value == "ADDON_LOADED")
    event = nil
end
function frame:SetScript(kind, fn)
    assert(kind == "OnEvent")
    callback = fn
end
function CreateFrame(kind)
    assert(kind == "Frame")
    return frame
end
local name = assert(io.open("addon.json")):read("*a"):match('"name"%s*:%s*"([%w_]+)"')
local namespace = {}
assert(loadfile("Core.lua"))(name, namespace)
assert(event == "ADDON_LOADED")
callback(frame, event, "AnotherAddon")
assert(namespace.db == nil)
callback(frame, event, name)
assert(namespace.db.schemaVersion == 1)
namespace.db.keepMe = true
-- Reloading must preserve saved data.
assert(loadfile("Core.lua"))(name, namespace)
callback(frame, event, name)
assert(namespace.db.keepMe == true)
print("Addon initialization and saved data checks passed")
