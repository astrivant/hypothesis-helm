-- Compute the existing component-wise upper bound using Lua 5.4 integers.
-- Data is transferred once per analysis. No template strings are evaluated.
local maximum_integer = math.maxinteger

return function(components)
    return function(assigned)
        local totals = {}
        for component_index = 1, #components do
            local component = components[component_index]
            local factors, cases = component.factors, component.cases
            local maxima = {}
            local possible = false
            for case_index = 1, #cases do
                local case = cases[case_index]
                local compatible = true
                for position = 1, #factors do
                    local selected = assigned[factors[position]]
                    -- Domain index zero is an ordinary assignment, not an absent key.
                    if selected ~= nil and selected ~= case.choices[position] then
                        compatible = false
                        break
                    end
                end
                if compatible then
                    possible = true
                    for level = 1, #case.levels do
                        local count = case.levels[level]
                        if maxima[level] == nil or count > maxima[level] then
                            maxima[level] = count
                        end
                    end
                end
            end
            if not possible then
                return -1
            end
            for level = 1, #maxima do
                local previous = totals[level] or 0
                if maxima[level] > maximum_integer - previous then
                    return nil -- Python's unbounded integers remain authoritative.
                end
                totals[level] = previous + maxima[level]
            end
        end
        local breadth, depth = 0, #totals
        for level = 1, depth do
            if totals[level] > breadth then
                breadth = totals[level]
            end
        end
        if depth > 0 and breadth > maximum_integer // depth then
            return nil
        end
        return breadth * depth
    end
end
