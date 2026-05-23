local mp = require 'mp'
local utils = require 'mp.utils'

function on_file_loaded()
    -- Path on the Pi
    local path = "/home/pi/museum_signage/public/audio_config.json"
    local f = io.open(path, "r")
    if not f then
        -- Fallback to local path for testing
        path = "public/audio_config.json"
        f = io.open(path, "r")
    end
    
    if not f then
        mp.msg.warn("Could not find audio_config.json")
        return
    end
    
    local content = f:read("*all")
    f:close()
    
    -- Retrieve screen index (1 or 2) passed from script-opts
    local screen = mp.get_opt("screen") or "1"
    local filename = mp.get_property("filename")
    
    if not filename then return end
    
    -- Extract the JSON section for our specific screen using balanced braces match %b{}
    local screen_section = content:match('"screen' .. screen .. '"%s*:%s*(%b{})')
    if not screen_section then
        mp.msg.warn("Could not find screen" .. screen .. " section in config")
        return
    end
    
    -- Check if global mute is active
    local global_mute = screen_section:match('"global_mute"%s*:%s*(%a+)') == "true"
    
    -- Check if the current filename has a custom clip setting
    local escaped_fn = filename:gsub("[%-%.%+%*%?%[%]%^%$%(%)%%]", "%%%1")
    local clip_mute = false
    
    local clip_match = screen_section:match('"' .. escaped_fn .. '"%s*:%s*(%b{})')
    if clip_match then
        clip_mute = clip_match:match('"mute"%s*:%s*(%a+)') == "true"
    end
    
    -- Apply final mute state to player
    local final_mute = global_mute or clip_mute
    mp.set_property_bool("mute", final_mute)
    
    mp.msg.info(string.format(
        "File: %s | Screen: %s | Global Mute: %s | Clip Mute: %s | Final: %s",
        filename, screen, tostring(global_mute), tostring(clip_mute), tostring(final_mute)
    ))
end

-- Hook into file-loaded event to apply mute settings instantly when video changes
mp.register_event("file-loaded", on_file_loaded)
