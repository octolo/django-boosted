/*global DateTimeShortcuts, SelectFilter, django */
"use strict";
{
    const addHolders = new WeakMap();

    const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

    const managementInput = (group, suffix) => {
        return Array.from(group.querySelectorAll(`input[name$="-${suffix}"]`)).find((input) => {
            return input.closest("[data-inline-type]") === group;
        });
    };

    const managementPrefix = (group) => {
        const total = managementInput(group, "TOTAL_FORMS");
        return total ? total.name.slice(0, -"-TOTAL_FORMS".length) : "";
    };

    const managementValue = (group, suffix) => {
        const input = managementInput(group, suffix);
        return input ? input.value : "";
    };

    const inlineOptions = (group) => {
        const payload = JSON.parse(group.getAttribute("data-inline-formset") || "{}");
        const options = payload.options || {};
        options.prefix = managementPrefix(group);
        return options;
    };

    const closestGroup = (element) => {
        const parent = element.parentElement;
        return parent ? parent.closest("[data-inline-type]") : null;
    };

    const directRows = (group) => {
        if (group.dataset.inlineType === "tabular") {
            const body = group.querySelector("tbody");
            if (!body) {
                return [];
            }
            return Array.from(body.children).filter((row) => row.classList.contains("form-row"));
        }
        return Array.from(group.querySelectorAll(".inline-related")).filter((row) => {
            return closestGroup(row) === group;
        });
    };

    const activeRows = (group) => {
        return directRows(group).filter((row) => {
            return !row.hidden && !row.classList.contains("empty-form");
        });
    };

    const rowControl = (row, selector) => {
        return Array.from(row.querySelectorAll(selector)).find((node) => {
            return node.closest(".inline-related, tr.form-row") === row;
        });
    };

    const directNodes = (group, container, selector) => {
        return Array.from(container.querySelectorAll(selector)).filter((node) => {
            return node.closest("[data-inline-type]") === group;
        });
    };

    const initAutocomplete = (group, row) => {
        if (!window.django || !window.django.jQuery) {
            return;
        }
        const $ = window.django.jQuery;
        directNodes(group, row, ".admin-autocomplete").forEach((node) => {
            $(node).djangoAdminSelect2();
        });
    };

    const initPrepopulatedFields = (group, row) => {
        if (!window.django || !window.django.jQuery) {
            return;
        }
        const $ = window.django.jQuery;
        const fields = inlineOptions(group).prepopulatedFields || {};
        Object.entries(fields).forEach(([name, options]) => {
            const targets = directNodes(
                group,
                row,
                `.field-${CSS.escape(name)} input, .field-${CSS.escape(name)} select, .field-${CSS.escape(name)} textarea`,
            );
            if (!targets.length) {
                return;
            }
            const dependencies = options.dependencies.map((dependency) => {
                const fields = directNodes(
                    group,
                    row,
                    `.field-${CSS.escape(dependency)} input, .field-${CSS.escape(dependency)} select, .field-${CSS.escape(dependency)} textarea`,
                );
                return fields.length ? `#${fields[0].id}` : null;
            }).filter(Boolean);
            const target = $(targets[0]);
            if (dependencies.length && typeof target.prepopulate === "function") {
                target.prepopulate(
                    dependencies,
                    options.maxLength,
                    options.allowUnicode,
                );
            }
        });
    };

    const initSelectFilters = (group, row) => {
        if (typeof SelectFilter === "undefined") {
            return;
        }
        directNodes(group, row, ".selectfilter, .selectfilterstacked").forEach((node) => {
            SelectFilter.init(
                node.id,
                node.dataset.fieldName,
                node.classList.contains("selectfilterstacked"),
            );
        });
    };

    const initWidgets = (group, row, includeAutocomplete = true) => {
        if (includeAutocomplete) {
            initAutocomplete(group, row);
        }
        initPrepopulatedFields(group, row);
        initSelectFilters(group, row);
    };

    const rewritePrefix = (root, prefix, index) => {
        const pattern = new RegExp(`${escapeRegExp(prefix)}-__prefix__`, "g");
        const replacement = `${prefix}-${index}`;
        [root, ...root.querySelectorAll("*")].forEach((node) => {
            ["id", "name", "for"].forEach((attribute) => {
                const value = node.getAttribute(attribute);
                if (value && value.includes(`${prefix}-__prefix__`)) {
                    node.setAttribute(attribute, value.replace(pattern, replacement));
                }
            });
            const payload = node.getAttribute("data-inline-formset");
            if (payload && payload.includes(`${prefix}-__prefix__`)) {
                node.setAttribute("data-inline-formset", payload.replace(pattern, replacement));
            }
        });
    };

    const refreshDateTimeShortcuts = () => {
        if (typeof DateTimeShortcuts === "undefined") {
            return;
        }
        document.querySelectorAll(".datetimeshortcuts").forEach((node) => node.remove());
        DateTimeShortcuts.init();
    };

    const toggleControls = (group) => {
        const minValue = managementValue(group, "MIN_NUM_FORMS");
        const maxValue = managementValue(group, "MAX_NUM_FORMS");
        const active = activeRows(group);
        const hideRemoves = minValue !== "" && active.length <= Number(minValue);
        active.forEach((row) => {
            const link = rowControl(row, ".boosted-nested-remove");
            if (link) {
                link.hidden = hideRemoves;
            }
        });
        const holder = addHolders.get(group);
        if (holder) {
            holder.hidden = maxValue !== "" && active.length >= Number(maxValue);
        }
    };

    const hideRow = (group, row) => {
        let deletion = rowControl(row, 'input[name$="-DELETE"]');
        if (!deletion) {
            deletion = document.createElement("input");
            deletion.type = "hidden";
            deletion.name = `${row.id}-DELETE`;
            deletion.value = "on";
            deletion.className = "boosted-nested-delete";
            const container = row.querySelector(".delete") || row;
            container.append(deletion);
        } else {
            deletion.checked = true;
        }
        row.hidden = true;
        const nested = row.nextElementSibling;
        if (nested && nested.classList.contains("boosted-nested-inline-row")) {
            nested.hidden = true;
        }
        const errors = row.previousElementSibling;
        if (errors && errors.classList.contains("row-form-errors")) {
            errors.hidden = true;
        }
        precedingCompanionRows(row).forEach((companion) => {
            companion.hidden = true;
        });
        toggleControls(group);
        document.dispatchEvent(new CustomEvent("formset:removed", {
            detail: {formsetName: managementPrefix(group)},
        }));
    };

    const initGroup = (group, dynamic = false) => {
        if (group.dataset.boostedNestedInitialized === "true" || group.closest(".empty-form")) {
            return;
        }
        if (group.dataset.boostedNestedFormset === "true") {
            initNestedOwner(group, dynamic);
        } else if (group.dataset.boostedDeferredLeaf === "true") {
            initLeaf(group, dynamic);
        }
        if (!dynamic && group.dataset.boostedNestedLevel === "true") {
            activeRows(group).forEach((row) => initPrepopulatedFields(group, row));
        }
    };

    const initContainedGroups = (container, dynamic = false) => {
        container.querySelectorAll("[data-inline-type]").forEach((group) => {
            initGroup(group, dynamic);
        });
    };

    const precedingCompanionRows = (row) => {
        const rows = [];
        let previous = row.previousElementSibling;
        if (previous && previous.classList.contains("row-form-errors")) {
            previous = previous.previousElementSibling;
        }
        while (previous && previous.classList.contains("boosted-nested-form-companion")) {
            rows.unshift(previous);
            previous = previous.previousElementSibling;
        }
        return rows;
    };

    const addRow = (group) => {
        const rows = directRows(group);
        const template = rows.find((row) => row.classList.contains("empty-form"));
        if (!template) {
            return;
        }
        const prefix = managementPrefix(group);
        const total = managementInput(group, "TOTAL_FORMS");
        const index = Number(total.value);
        const row = template.cloneNode(true);
        row.classList.remove("empty-form", "last-related");
        row.hidden = false;
        row.id = `${prefix}-${index}`;
        const nested = template.nextElementSibling;
        const nestedClone = nested && nested.classList.contains("boosted-nested-inline-row")
            ? nested.cloneNode(true)
            : null;
        if (nestedClone) {
            nestedClone.classList.remove("empty-form");
            nestedClone.hidden = false;
        }
        const templateHeadings = precedingCompanionRows(template);
        const anchor = templateHeadings[0] || template;
        templateHeadings.forEach((heading) => {
            const headingClone = heading.cloneNode(true);
            headingClone.classList.remove("empty-form");
            const number = headingClone.querySelector(".boosted-nested-object-number");
            if (number) {
                number.textContent = String(index + 1);
            }
            headingClone.hidden = false;
            template.parentNode.insertBefore(headingClone, anchor);
        });
        template.parentNode.insertBefore(row, anchor);
        if (nestedClone) {
            template.parentNode.insertBefore(nestedClone, anchor);
        }
        rewritePrefix(row, prefix, index);
        if (nestedClone) {
            rewritePrefix(nestedClone, prefix, index);
        }
        total.value = String(index + 1);
        initContainedGroups(row, true);
        if (nestedClone) {
            initContainedGroups(nestedClone, true);
        }
        initWidgets(group, row, false);
        toggleControls(group);
        refreshDateTimeShortcuts();
        const nestedAutocompletes = Array.from(
            row.querySelectorAll(".admin-autocomplete"),
        ).filter((node) => node.closest("[data-inline-type]") !== group);
        nestedAutocompletes.forEach((node) => node.classList.remove("admin-autocomplete"));
        row.dispatchEvent(new CustomEvent("formset:added", {
            bubbles: true,
            detail: {formsetName: prefix},
        }));
        nestedAutocompletes.forEach((node) => node.classList.add("admin-autocomplete"));
    };

    const initNestedOwner = (group, dynamic = false) => {
        group.dataset.boostedNestedInitialized = "true";
        group.addEventListener("click", (event) => {
            const remove = event.target.closest(".boosted-nested-remove");
            if (!remove || remove.closest("[data-boosted-nested-formset]") !== group) {
                return;
            }
            const row = remove.closest(".inline-related, tr.form-row");
            if (!row || row.classList.contains("empty-form") || !directRows(group).includes(row)) {
                return;
            }
            event.preventDefault();
            hideRow(group, row);
        });
        const options = inlineOptions(group);
        const tabular = group.dataset.inlineType === "tabular";
        const emptyRow = directRows(group).find((row) => row.classList.contains("empty-form"));
        const container = tabular ? group.querySelector("tbody") : group.querySelector("fieldset");
        if (!container) {
            return;
        }
        const holder = document.createElement(tabular ? "tr" : "div");
        holder.className = "add-row";
        const link = document.createElement("a");
        link.href = "#";
        link.className = "addlink";
        link.setAttribute("role", "button");
        link.textContent = options.addText || "Add another";
        link.addEventListener("click", (event) => {
            event.preventDefault();
            addRow(group);
        });
        if (tabular) {
            const cell = document.createElement("td");
            cell.colSpan = emptyRow ? emptyRow.children.length : 1;
            cell.append(link);
            holder.append(cell);
        } else {
            holder.append(link);
        }
        container.append(holder);
        addHolders.set(group, holder);
        toggleControls(group);
        initContainedGroups(group, dynamic);
        if (dynamic) {
            activeRows(group).forEach((row) => initWidgets(group, row));
        }
    };

    const initLeaf = (group, dynamic = false) => {
        if (!window.django || !window.django.jQuery) {
            return;
        }
        group.dataset.boostedNestedInitialized = "true";
        const options = inlineOptions(group);
        const $ = window.django.jQuery;
        const scope = `#${CSS.escape(group.id)}`;
        if (group.dataset.inlineType === "stacked") {
            const selector = `${scope} .inline-related`;
            $(selector).stackedFormset(selector, options);
        } else {
            const selector = `${scope} .tabular.inline-related tbody:first > tr.form-row`;
            $(selector).tabularFormset(selector, options);
        }
        if (dynamic) {
            activeRows(group).forEach((row) => initWidgets(group, row));
        }
    };

    const stripTemplateLeaves = () => {
        document.querySelectorAll(".empty-form .js-inline-admin-formset").forEach((group) => {
            group.classList.remove("js-inline-admin-formset");
            group.dataset.boostedDeferredLeaf = "true";
        });
    };

    document.addEventListener("formset:added", (event) => {
        const row = event.target;
        if (!row.closest) {
            return;
        }
        const group = row.closest("[data-inline-type]");
        if (
            group
            && group.dataset.boostedNestedLevel === "true"
            && group.dataset.boostedNestedFormset !== "true"
        ) {
            initPrepopulatedFields(group, row);
        }
    });

    const boot = () => {
        stripTemplateLeaves();
        document.querySelectorAll("[data-boosted-nested-formset]").forEach((group) => {
            initGroup(group);
        });
    };

    // Capture runs before Django's bubble-phase inline initializer.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot, true);
    } else {
        boot();
    }
}
